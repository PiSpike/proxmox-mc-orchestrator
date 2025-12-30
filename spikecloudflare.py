import os
from cloudflare import Cloudflare

# Configuration
CF_TOKEN = os.environ.get('CF_TOKEN')
ZONE_ID = os.environ.get('ZONE_ID')
BASE_DOMAIN = "spikenet.net"
DDNS_TARGET = "home.spikenet.net"
# Initialize the client correctly
client = Cloudflare(api_token=CF_TOKEN)

def create_subdomain(subdomain_prefix):
    full_name = f"{subdomain_prefix}.{BASE_DOMAIN}"
    
    try:
        # 1. Check if record already exists
        records = client.dns.records.list(zone_id=ZONE_ID, name=full_name)
        for record in records:
            print(f"DNS Record for {full_name} already exists.")
            return True

        # 2. Create the CNAME record
        client.dns.records.create(
            zone_id=ZONE_ID,
            name=subdomain_prefix,
            type="CNAME",
            content=DDNS_TARGET,
            proxied=False
        )
        
        print(f"Successfully linked {full_name}")
        return True
    except Exception as e:
        print(f"Cloudflare Error: {e}")
        return False

def remove_subdomain(subdomain_prefix):
    full_name = f"{subdomain_prefix}.{BASE_DOMAIN}"
    
    try:
        # 1. Search for the record
        records = client.dns.records.list(zone_id=ZONE_ID, name=full_name)
        
        found = False
        for record in records:
            # 2. Delete using the record ID
            client.dns.records.delete(dns_record_id=record.id, zone_id=ZONE_ID)
            print(f"Successfully deleted DNS record: {full_name} (ID: {record.id})")
            found = True
        
        if not found:
            print(f"No DNS record found for {full_name}.")
            
        return True

    except Exception as e:
        print(f"Cloudflare Delete Error: {e}")
        return False