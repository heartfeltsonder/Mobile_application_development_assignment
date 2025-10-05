import sqlite3

schema = """
DROP TABLE IF EXISTS invoices;

CREATE TABLE invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id TEXT NOT NULL,
    payload TEXT,              -- raw JSON invoice
    status TEXT NOT NULL,
    authority_ref TEXT,        -- reference from tax authority
    total REAL,
    tax_total REAL,
    created_at TEXT
);

DROP TABLE IF EXISTS items;

CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id TEXT NOT NULL,
    item_name TEXT,
    qty INTEGER,
    rate REAL,
    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
);
"""

if __name__ == "__main__":
    conn = sqlite3.connect("studentc.db")
    cur = conn.cursor()
    cur.executescript(schema)
    conn.commit()
    conn.close()
    print("✅ Database reset with invoices.payload and invoices.authority_ref")
