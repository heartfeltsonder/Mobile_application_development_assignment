DROP TABLE IF EXISTS invoices;

CREATE TABLE invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id TEXT NOT NULL,
    status TEXT NOT NULL,
    authority_ref TEXT,
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
