"""
Synthetic Customer Generator
Generates realistic customer entities with internally consistent payment histories and fatigue markers.
"""

import random
from typing import List, Dict, Any
from backend.seed.config import GeneratorConfig
from backend.models.enums import CustomerType

FIRST_NAMES = [
    "Aarav", "Priya", "Rohan", "Ananya", "Vikram", "Sneha", "Karan", "Pooja",
    "Aditya", "Neha", "Rahul", "Kavya", "Siddharth", "Riya", "Amit", "Divya",
    "Manish", "Isha", "Deepak", "Tanvi", "Sanjay", "Meera", "Varun", "Simran",
]

LAST_NAMES = [
    "Sharma", "Patel", "Singh", "Kumar", "Gupta", "Shah", "Verma", "Joshi",
    "Mehta", "Rao", "Nair", "Das", "Reddy", "Choubey", "Chopra", "Deshmukh",
]

def generate_customers(config: GeneratorConfig, rng: random.Random) -> List[Dict[str, Any]]:
    """Generate a reproducible list of customer profile records."""
    customers = []
    
    for i in range(1, config.total_customers + 1):
        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)
        full_name = f"{first_name} {last_name}"
        email = f"{first_name.lower()}.{last_name.lower()}{i}@example.com"
        phone = f"+9198{rng.randint(10000000, 99999999)}"
        
        # Roll customer type based on probability distribution
        cust_type_roll = rng.random()
        if cust_type_roll < config.customer_type_distribution["NEW"]:
            cust_type = CustomerType.NEW.value
        elif cust_type_roll < config.customer_type_distribution["NEW"] + config.customer_type_distribution["RETURNING"]:
            cust_type = CustomerType.RETURNING.value
        else:
            cust_type = CustomerType.FATIGUED.value

        # Generate internally consistent history attributes based on customer type
        if cust_type == CustomerType.NEW.value:
            account_age_days = rng.randint(1, 30)
            prev_txns = rng.randint(0, 2)
            prev_fails = rng.randint(0, prev_txns)
            prev_succ = prev_txns - prev_fails
            prev_rec = 0
            contacts_24h = rng.randint(0, 1)
        elif cust_type == CustomerType.RETURNING.value:
            account_age_days = rng.randint(31, 365)
            prev_txns = rng.randint(3, 25)
            prev_fails = rng.randint(0, max(1, prev_txns // 3))
            prev_succ = prev_txns - prev_fails
            prev_rec = rng.randint(0, prev_fails)
            contacts_24h = rng.randint(0, 2)
        else: # FATIGUED
            account_age_days = rng.randint(60, 400)
            prev_txns = rng.randint(5, 30)
            prev_fails = rng.randint(4, prev_txns)
            prev_succ = prev_txns - prev_fails
            prev_rec = rng.randint(0, min(1, prev_fails))
            contacts_24h = rng.randint(3, 6) # High contact count

        avg_amount_paise = rng.randint(30000, 1500000) # ₹300 to ₹15,000

        customer_record = {
            "id": f"cust_synth_{i:04d}",
            "name": full_name,
            "email": email,
            "phone": phone,
            "customer_type": cust_type,
            "account_age_days": account_age_days,
            "previous_transaction_count": prev_txns,
            "previous_successful_payment_count": prev_succ,
            "previous_failed_payment_count": prev_fails,
            "previous_recovered_payment_count": prev_rec,
            "contacts_count_24h": contacts_24h,
            "historical_avg_amount_paise": avg_amount_paise,
        }
        customers.append(customer_record)

    return customers
