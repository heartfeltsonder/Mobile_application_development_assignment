import os
import json
from datetime import datetime, date
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import requests
from dotenv import load_dotenv


TAX_API_URL = os.getenv("TAX_API_URL", "https://example.mock.pstmn.io/tax/submit")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///studentc.db")


Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(String, unique=True, index=True)
    payload = Column(Text)
    status = Column(String, default="PENDING")
    authority_ref = Column(String, nullable=True)
    total = Column(Float, default=0.0)
    tax_total = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)


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

class InvoicePayload(BaseModel):
    seller: Seller
    buyer: Buyer
    invoiceDate: str
    invoiceId: str
    paid: str
    isPaid: str
    comment: Optional[str] = None
    cardAcceptable: Optional[str] = None
    total: List[Total]
    items: List[Item]


app = FastAPI(title="Invoice & Tax Integration Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For demo; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@app.get("/ping")
def ping():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.post("/api/v1/seed")
def seed_demo_data(db: Session = Depends(get_db)):
    demo_invoices = [
        {
            "invoice_id": "INV-2025-1001",
            "payload": json.dumps({"seller": "Demo Ltd", "buyer": "Client A"}),
            "total": 116.0,
            "tax_total": 16.0,
            "status": "DRAFT",
        },
        {
            "invoice_id": "INV-2025-1002",
            "payload": json.dumps({"seller": "Demo Ltd", "buyer": "Client B"}),
            "total": 58.0,
            "tax_total": 8.0,
            "status": "DRAFT",
        },
    ]

    for inv in demo_invoices:
        existing = db.query(Invoice).filter_by(invoice_id=inv["invoice_id"]).first()
        if not existing:
            db.add(Invoice(**inv))
    db.commit()
    return {"message": "Seed data created"}


@app.post("/api/v1/invoices/submit")
def submit_invoice(payload: InvoicePayload, mode: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """
    Submits an invoice to the Tax Authority (Mock API).
    Mode (optional): 'success', 'validation_error', 'error', 'duplicate'
    """
    invoice_id = payload.invoiceId
    total_value = payload.total[0].total if payload.total else 0
    tax_value = payload.total[0].tax_total if payload.total else 0

    invoice = db.query(Invoice).filter_by(invoice_id=invoice_id).first()
    if not invoice:
        invoice = Invoice(invoice_id=invoice_id)

    try:
        
        url = TAX_API_URL
        if mode:
            url += f"?mode={mode}"

        response = requests.post(url, json=payload.dict())
        response.raise_for_status()
        data = response.json()

        invoice.status = data.get("status", "SUBMITTED")
        invoice.authority_ref = data.get("authority_ref", "")
        invoice.payload = payload.json()
        invoice.total = total_value
        invoice.tax_total = tax_value
        db.add(invoice)
        db.commit()

        return {
            "invoice_id": invoice_id,
            "status": invoice.status,
            "authority_ref": invoice.authority_ref,
            "response": data,
        }

    except requests.exceptions.RequestException as e:
        invoice.status = "FAILED"
        db.add(invoice)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Submission failed: {str(e)}")


@app.get("/api/v1/invoices/{invoice_id}/status")
def get_invoice_status(invoice_id: str, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter_by(invoice_id=invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {
        "invoice_id": invoice.invoice_id,
        "status": invoice.status,
        "total": invoice.total,
        "tax_total": invoice.tax_total,
        "authority_ref": invoice.authority_ref,
        "created_at": invoice.created_at,
    }


@app.get("/api/v1/reports/daily")
def daily_report(db: Session = Depends(get_db)):
    today = date.today()
    invoices = db.query(Invoice).all()
    total_sales = sum(inv.total for inv in invoices)
    total_tax = sum(inv.tax_total for inv in invoices)
    count = len(invoices)
    return {
        "date": today.isoformat(),
        "total_sales": total_sales,
        "total_tax": total_tax,
        "invoices_count": count,
    }


# Run manually: uvicorn backend:app --reload --port 8000
