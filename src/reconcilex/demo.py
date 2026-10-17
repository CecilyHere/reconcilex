"""Synthetic demonstration fixtures; no real customers or banking records."""

LEDGER = '''id,date,amount,currency,reference,description
L001,2026-01-05,100.00,SGD,SALE-100,Synthetic customer payment
L002,2026-01-06,-25.50,SGD,VEND-200,Synthetic supplier payment
L003,2026-01-07,80.00,SGD,,Unreferenced receipt
L004,2026-01-08,45.00,SGD,SALE-400,Receipt with fee difference
L005,2026-01-09,-9.00,SGD,VEND-500,Ledger-only payment
L006,2026-01-10,150.00,USD,USD-600,Synthetic USD receipt
L007,2026-01-11,0.00,SGD,ZERO-700,Zero-value adjustment
L008,2026-01-12,10.00,SGD,LEDGER-REF,Conflicting reference
'''
BANK = '''id,date,amount,currency,reference,description
B001,2026-01-05,100.00,SGD,SALE-100,Synthetic bank credit
B002,2026-01-07,-25.50,SGD,VEND-200,Synthetic bank debit
B003,2026-01-07,80.00,SGD,,Possible first receipt
B004,2026-01-07,80.00,SGD,,Possible second receipt
B005,2026-01-08,44.98,SGD,SALE-400,Net receipt
B006,2026-01-10,150.00,USD,USD-600,Synthetic USD credit
B007,2026-01-11,0.00,SGD,ZERO-700,Zero bank entry
B008,2026-01-12,10.00,SGD,BANK-REF,Conflicting bank reference
B009,2026-01-15,-5.00,SGD,BANK-FEE,Synthetic bank-only fee
'''
CONFIG = {"date_window_days": 3, "amount_tolerance": "0.05"}
EXPECTED = {"ledger_rows": 8, "bank_rows": 9, "matched_pairs": 3,
            "review_candidates": 4, "remaining_ledger": 5, "remaining_bank": 6}
