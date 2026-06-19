"""
VAT MOSS (Mini One-Stop Shop) Reporting
Quarterly VAT filing for Danish SKAT
Compliance: EU VAT Directive 2008/8/EC
"""

import psycopg2
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os

class VATMOSSReporter:
    """
    Generate VAT MOSS reports for quarterly filing
    Denmark is the Member State of Identification (MSI)
    """
    
    def __init__(self, database_url: str, vat_number: str = "DK12345678"):
        """
        Initialize VAT MOSS reporter
        
        Args:
            database_url: PostgreSQL connection string
            vat_number: Danish VAT number (DK + 8 digits)
        """
        self.database_url = database_url
        self.vat_number = vat_number
        
        if not vat_number.startswith("DK") or len(vat_number) != 10:
            raise ValueError("Invalid Danish VAT number format. Must be DK + 8 digits")
    
    def get_quarter_dates(self, quarter: str) -> Tuple[datetime, datetime]:
        """
        Get start and end dates for a quarter
        
        Args:
            quarter: Format '2026-Q2'
            
        Returns:
            Tuple of (start_date, end_date)
        """
        
        year, q = quarter.split('-Q')
        year = int(year)
        q = int(q)
        
        if q == 1:
            start = datetime(year, 1, 1)
            end = datetime(year, 3, 31, 23, 59, 59)
        elif q == 2:
            start = datetime(year, 4, 1)
            end = datetime(year, 6, 30, 23, 59, 59)
        elif q == 3:
            start = datetime(year, 7, 1)
            end = datetime(year, 9, 30, 23, 59, 59)
        elif q == 4:
            start = datetime(year, 10, 1)
            end = datetime(year, 12, 31, 23, 59, 59)
        else:
            raise ValueError(f"Invalid quarter: {q}. Must be 1-4")
        
        return start, end
    
    def collect_transactions(self, quarter: str) -> List[Dict]:
        """
        Collect all VAT transactions for a quarter
        
        Args:
            quarter: Format '2026-Q2'
            
        Returns:
            List of transaction summaries by country
        """
        
        start_date, end_date = self.get_quarter_dates(quarter)
        
        conn = psycopg2.connect(self.database_url)
        cur = conn.cursor()
        
        # Aggregate transactions by country
        cur.execute("""
            SELECT 
                country_code,
                COUNT(*) as transaction_count,
                SUM(amount_net) as total_net,
                AVG(vat_rate) as vat_rate,
                SUM(vat_amount) as total_vat,
                SUM(total_amount) as total_gross
            FROM vat_transactions
            WHERE created_at >= %s AND created_at <= %s
            GROUP BY country_code
            ORDER BY country_code
        """, (start_date, end_date))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        transactions = []
        for row in rows:
            transactions.append({
                "country_code": row[0],
                "transaction_count": row[1],
                "total_net": float(row[2]),
                "vat_rate": float(row[3]),
                "total_vat": float(row[4]),
                "total_gross": float(row[5])
            })
        
        return transactions
    
    def generate_xml_report(self, quarter: str) -> str:
        """
        Generate VAT MOSS XML report for SKAT submission
        
        Args:
            quarter: Format '2026-Q2'
            
        Returns:
            XML string
        """
        
        transactions = self.collect_transactions(quarter)
        
        if not transactions:
            raise ValueError(f"No transactions found for quarter {quarter}")
        
        # Create XML structure
        root = ET.Element('VATReturn', {
            'xmlns': 'urn:eu:taxud:vat:moss:v1',
            'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        })
        
        # Header
        header = ET.SubElement(root, 'Header')
        ET.SubElement(header, 'MessageRefId').text = f"{quarter}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        ET.SubElement(header, 'Timestamp').text = datetime.utcnow().isoformat() + 'Z'
        
        # Body
        body = ET.SubElement(root, 'VATReturnBody')
        ET.SubElement(body, 'ReportingPeriod').text = quarter
        
        # Supplier identification
        supplier = ET.SubElement(body, 'SupplierVATIdentification')
        ET.SubElement(supplier, 'VATNumber').text = self.vat_number
        
        # Lines (one per country)
        for tx in transactions:
            line = ET.SubElement(body, 'Line')
            ET.SubElement(line, 'MemberState').text = tx['country_code']
            ET.SubElement(line, 'VATRate').text = f"{tx['vat_rate']:.4f}"
            ET.SubElement(line, 'TaxableAmount').text = f"{tx['total_net']:.2f}"
            ET.SubElement(line, 'VATAmount').text = f"{tx['total_vat']:.2f}"
        
        # Total
        total_vat = sum(tx['total_vat'] for tx in transactions)
        ET.SubElement(body, 'TotalVATAmount').text = f"{total_vat:.2f}"
        
        # Pretty print XML
        xml_str = ET.tostring(root, encoding='unicode')
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent="  ")
    
    def generate_csv_report(self, quarter: str) -> str:
        """
        Generate CSV report for internal review
        
        Args:
            quarter: Format '2026-Q2'
            
        Returns:
            CSV string
        """
        
        transactions = self.collect_transactions(quarter)
        
        csv_lines = [
            "Country,Transactions,Net Amount (EUR),VAT Rate,VAT Amount (EUR),Gross Amount (EUR)"
        ]
        
        for tx in transactions:
            csv_lines.append(
                f"{tx['country_code']},"
                f"{tx['transaction_count']},"
                f"{tx['total_net']:.2f},"
                f"{tx['vat_rate']:.4f},"
                f"{tx['total_vat']:.2f},"
                f"{tx['total_gross']:.2f}"
            )
        
        # Add totals
        total_transactions = sum(tx['transaction_count'] for tx in transactions)
        total_net = sum(tx['total_net'] for tx in transactions)
        total_vat = sum(tx['total_vat'] for tx in transactions)
        total_gross = sum(tx['total_gross'] for tx in transactions)
        
        csv_lines.append("")
        csv_lines.append(
            f"TOTAL,"
            f"{total_transactions},"
            f"{total_net:.2f},"
            f"-,"
            f"{total_vat:.2f},"
            f"{total_gross:.2f}"
        )
        
        return "\n".join(csv_lines)
    
    def validate_location_proofs(self, quarter: str) -> Dict:
        """
        Validate that all transactions have 2 location proofs
        Required by VAT MOSS rules
        
        Args:
            quarter: Format '2026-Q2'
            
        Returns:
            Validation report
        """
        
        start_date, end_date = self.get_quarter_dates(quarter)
        
        conn = psycopg2.connect(self.database_url)
        cur = conn.cursor()
        
        # Check for missing location proofs
        cur.execute("""
            SELECT id, country_code, location_proof_1, location_proof_2
            FROM vat_transactions
            WHERE created_at >= %s AND created_at <= %s
              AND (location_proof_1 IS NULL OR location_proof_2 IS NULL)
        """, (start_date, end_date))
        
        invalid_transactions = cur.fetchall()
        
        # Check for duplicate proofs (not allowed)
        cur.execute("""
            SELECT id, country_code, location_proof_1, location_proof_2
            FROM vat_transactions
            WHERE created_at >= %s AND created_at <= %s
              AND location_proof_1 = location_proof_2
        """, (start_date, end_date))
        
        duplicate_proofs = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "valid": len(invalid_transactions) == 0 and len(duplicate_proofs) == 0,
            "invalid_transactions": len(invalid_transactions),
            "duplicate_proofs": len(duplicate_proofs),
            "details": {
                "missing_proofs": [str(tx[0]) for tx in invalid_transactions],
                "duplicate_proofs": [str(tx[0]) for tx in duplicate_proofs]
            }
        }
    
    def get_filing_deadline(self, quarter: str) -> datetime:
        """
        Get filing deadline for a quarter
        VAT MOSS deadline: 20th day of month following quarter end
        
        Args:
            quarter: Format '2026-Q2'
            
        Returns:
            Deadline datetime
        """
        
        year, q = quarter.split('-Q')
        year = int(year)
        q = int(q)
        
        if q == 1:
            deadline = datetime(year, 4, 20)
        elif q == 2:
            deadline = datetime(year, 7, 20)
        elif q == 3:
            deadline = datetime(year, 10, 20)
        elif q == 4:
            deadline = datetime(year + 1, 1, 20)
        
        return deadline
    
    def generate_summary(self, quarter: str) -> Dict:
        """
        Generate summary report for quarter
        
        Args:
            quarter: Format '2026-Q2'
            
        Returns:
            Summary dict
        """
        
        transactions = self.collect_transactions(quarter)
        validation = self.validate_location_proofs(quarter)
        deadline = self.get_filing_deadline(quarter)
        
        total_vat = sum(tx['total_vat'] for tx in transactions)
        total_transactions = sum(tx['transaction_count'] for tx in transactions)
        
        return {
            "quarter": quarter,
            "filing_deadline": deadline.isoformat(),
            "days_until_deadline": (deadline - datetime.now()).days,
            "total_vat_eur": round(total_vat, 2),
            "total_transactions": total_transactions,
            "countries": len(transactions),
            "validation": validation,
            "ready_to_file": validation['valid']
        }


# ============================================================================
# CLI TOOL
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python vat_moss.py <quarter> [command]")
        print("Quarter format: 2026-Q2")
        print("Commands: xml, csv, validate, summary (default: summary)")
        sys.exit(1)
    
    quarter = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else "summary"
    
    # Mock database URL (replace with actual)
    database_url = os.getenv("DATABASE_URL", "postgresql://localhost/eu_sound_lab")
    vat_number = os.getenv("VAT_NUMBER", "DK12345678")
    
    reporter = VATMOSSReporter(database_url, vat_number)
    
    if command == "xml":
        print(f"Generating VAT MOSS XML report for {quarter}...")
        xml = reporter.generate_xml_report(quarter)
        
        output_file = f"vat-moss-{quarter}.xml"
        with open(output_file, 'w') as f:
            f.write(xml)
        
        print(f"✅ XML report saved: {output_file}")
    
    elif command == "csv":
        print(f"Generating CSV report for {quarter}...")
        csv = reporter.generate_csv_report(quarter)
        
        output_file = f"vat-moss-{quarter}.csv"
        with open(output_file, 'w') as f:
            f.write(csv)
        
        print(f"✅ CSV report saved: {output_file}")
        print("\nPreview:")
        print(csv)
    
    elif command == "validate":
        print(f"Validating transactions for {quarter}...")
        validation = reporter.validate_location_proofs(quarter)
        
        if validation['valid']:
            print("✅ All transactions valid")
        else:
            print(f"❌ Validation failed:")
            print(f"   Missing proofs: {validation['invalid_transactions']}")
            print(f"   Duplicate proofs: {validation['duplicate_proofs']}")
    
    elif command == "summary":
        print(f"Generating summary for {quarter}...")
        summary = reporter.generate_summary(quarter)
        
        print(f"\n📊 VAT MOSS Summary - {summary['quarter']}")
        print(f"   Filing deadline: {summary['filing_deadline']}")
        print(f"   Days until deadline: {summary['days_until_deadline']}")
        print(f"   Total VAT: €{summary['total_vat_eur']}")
        print(f"   Total transactions: {summary['total_transactions']}")
        print(f"   Countries: {summary['countries']}")
        print(f"   Ready to file: {'✅ Yes' if summary['ready_to_file'] else '❌ No'}")
        
        if not summary['validation']['valid']:
            print(f"\n⚠️  Validation issues:")
            print(f"   Missing proofs: {summary['validation']['invalid_transactions']}")
            print(f"   Duplicate proofs: {summary['validation']['duplicate_proofs']}")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
