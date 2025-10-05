from fastapi import FastAPI, Depends
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
import requests, time, random, os, datetime
from typing import List
from pydantic import BaseModel


DATABASE_URL = os.getenv("INVOICE_DB_PATH", "sqlite:///./studentc.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class InvoiceDB(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(String, unique=True, index=True)
    status = Column(String, default="PENDING")
    authority_ref = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    responses = relationship("InvoiceResponseDB", back_populates="invoice")

class InvoiceResponseDB(Base):
    __tablename__ = "invoice_responses"
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(String, ForeignKey("invoices.invoice_id"))
    attempt = Column(Integer)
    status_code = Column(Integer, nullable=True)
    response = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    invoice = relationship("InvoiceDB", back_populates="responses")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Seller(BaseModel):
    tin: str
    name: str

class Buyer(BaseModel):
    tin: str
    name: str

class Total(BaseModel):
    subtotal: float
    tax_total: float
    discount_total: float
    total: float
    vat: float
    payment_method: str

class Item(BaseModel):
    invoiceItemId: str
    itemId: str
    taxable: str
    rate: int
    itemName: str
    qty: int
    tags: str

class Invoice(BaseModel):
    seller: Seller
    buyer: Buyer
    invoiceDate: str
    invoiceId: int
    paid: str
    isPaid: str
    comment: str
    cardAcceptable: str
    total: List[Total]
    items: List[Item]


app = FastAPI(title="Tax Integration API")

class TaxAuthorityClient:
    def __init__(self, base_url, max_retries=3, backoff_base=2, timeout=5):
        self.base_url = base_url
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout = timeout

    def submit_invoice(self, invoice: dict, mode: str = "success"):
        url = f"{self.base_url}/tax/submit?mode={mode}"
        attempts_log = []

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(url, json=invoice, timeout=self.timeout)
                attempts_log.append({
                    "attempt": attempt,
                    "status_code": response.status_code,
                    "response": response.json() if response.content else None
                })

                if response.status_code == 200:
                    return "SUBMITTED", attempts_log
                if 400 <= response.status_code < 500:
                    return "FAILED", attempts_log

            except requests.exceptions.RequestException as e:
                attempts_log.append({
                    "attempt": attempt,
                    "status_code": None,
                    "response": str(e)
                })

            if attempt < self.max_retries:
                sleep_time = self.backoff_base ** attempt * random.uniform(0.5, 1.5)
                time.sleep(sleep_time)

        return "FAILED", attempts_log

TAX_API_URL = os.getenv("TAX_API_URL", "https://xxxx.mock.pstmn.io")
client = TaxAuthorityClient(TAX_API_URL)

@app.get("/ping")
async def ping():
    return {"status": "ok"}

@app.post("/api/v1/invoices/submit")
async def submit_invoice(invoice: Invoice, mode: str = "success", db: Session = Depends(get_db)):
    status, attempts = client.submit_invoice(invoice.dict(), mode=mode)

   
    inv = InvoiceDB(invoice_id=str(invoice.invoiceId), status=status)
    db.merge(inv)  
    db.commit()

    for att in attempts:
        resp = InvoiceResponseDB(
            invoice_id=str(invoice.invoiceId),
            attempt=att["attempt"],
            status_code=att["status_code"],
            response=att["response"]
        )
        db.add(resp)

    db.commit()
    return {"invoice_id": invoice.invoiceId, "status": status, "attempts": attempts}
