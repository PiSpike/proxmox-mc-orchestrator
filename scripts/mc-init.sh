#!/bin/bash

# --- CONFIGURATION ---
META_FILE="/root/metadata.txt"
FLAG_FILE="/var/log/mc_init_complete.log"
MC_DIR="/home/minecraft"
MAX_WAIT_SECONDS=60

# 1. Skip if already initialized (Prevents overwriting on reboot)
if [ -f "$FLAG_FILE" ]; then
    echo "Server already initialized. Skipping setup."
    exit 0
fi

echo "Starting Minecraft Server Initialization..."

# 2. Wait for the Metadata File (The Push might happen a few seconds after boot)
echo "Waiting for configuration data..."
COUNT=0
while [ ! -f "$META_FILE" ] && [ $COUNT -lt $MAX_WAIT_SECONDS ]; do
    sleep 1
    ((COUNT++))
    if [ $((COUNT % 5)) -eq 0 ]; then
        echo "Still waiting for metadata... ($COUNT/$MAX_WAIT_SECONDS)"
    fi
done

if [ ! -f "$META_FILE" ]; then
    echo "ERROR: Metadata file never arrived! Using Fallback Defaults."
    # Fallback values just in case
    SEED="random"
    MODE="survival"
    DIFFICULTY="normal"
    WHITELIST_ACTIVE="0"
    OWNER_NAME="Admin"
    UUID="00000000-0000-0000-0000-000000000000"
else
    echo "Metadata received. Loading variables..."
    # 'source' reads the key=value pairs from the file
    # We use 'tr' to delete any Windows-style carriage returns (\r)
    source <(tr -d '\r' < "$META_FILE")
fi

# 3. Network Setup (Manual IP from Hostname)
# Expected Hostname: mc-203-anything OR mc-203
# We extract the VMID (203) and use it for the IP (10.0.10.203)
VMID=$(hostname | grep -oP 'mc-\K[0-9]+')

if [[ "$VMID" =~ ^[0-9]+$ ]]; then
# Perform the math: VMID minus 200
    IP_SUFFIX=$((VMID - 200))
    
    # Safety check: Ensure the suffix isn't negative or zero
    if [ "$IP_SUFFIX" -lt 1 ]; then
        echo "WARNING: Calculated IP suffix $IP_SUFFIX is invalid. Using VMID as fallback."
        IP_SUFFIX=$VMID
    fi

    echo "Configuring network for IP: 10.0.10.$IP_SUFFIX (VMID: $VMID)..."
    
    # Apply IP to eth0
    ip addr add 10.0.10.$IP_SUFFIX/24 dev eth0 || echo "IP already set"
    ip link set eth0 up
    
    # Add Gateway (Assuming your bridge/gateway is .254)
    ip route add default via 10.0.10.254 || echo "Route already exists"
else
    echo "ERROR: Could not determine VMID for IP calculation."
fi
# 4. UUID Formatting (Ensure 8-4-4-4-12 dashed format)
# Mojang API often gives undashed UUIDs, but whitelist.json needs dashes.
# If the UUID is exactly 32 chars (undashed), we format it.
add_to_minecraft_json() {
    local file=$1
    local name=$2
    local uuid=$3
    local extra_fields=$4 # For ops.json (level, etc)

    # 1. Create the new entry as a JSON object
    # We use jq to build the object safely
    local new_entry=$(jq -n \
        --arg n "$name" \
        --arg u "$uuid" \
        "{\"name\": \$n, \"uuid\": \$u $extra_fields}")

    # 2. Check if the file exists and is valid JSON, otherwise start with empty array []
    if [ ! -s "$file" ]; then echo "[]" > "$file"; fi

    # 3. Append the new entry and remove duplicates based on UUID
    # This prevents adding the same person twice if the script runs again
    local tmp_file=$(mktemp)
    jq ". += [$new_entry] | unique_by(.uuid)" "$file" > "$tmp_file" && mv "$tmp_file" "$file"
}

if [ "$WHITELIST_ACTIVE" == "1" ]; then
    echo "Adding $OWNER_NAME to existing whitelist/ops..."
    
    # Format UUID if needed
    if [[ ${#UUID} -eq 32 ]]; then
        UUID="${UUID:0:8}-${UUID:8:4}-${UUID:12:4}-${UUID:16:4}-${UUID:20}"
    fi

    # Add to whitelist.json
    add_to_minecraft_json "$MC_DIR/whitelist.json" "$OWNER_NAME" "$UUID" ""
    
    # Add to ops.json with level 4
    add_to_minecraft_json "$MC_DIR/ops.json" "$OWNER_NAME" "$UUID" ", \"level\": 4, \"bypassesPlayerLimit\": false"
fi
# 6. Generate server.properties
# We write this fresh to ensure clean settings
echo "Generating server.properties..."
cat <<EOF > "$MC_DIR/server.properties"
server-port=25565
level-seed=$SEED
gamemode=$MODE
difficulty=$DIFFICULTY
white-list=$WL_VAL
enforce-whitelist=$ENF_VAL
online-mode=false
allow-flight=true
prevent-proxy-connections=false
network-compression-threshold=256
view-distance=8
simulation-distance=6
motd=$OWNER_NAME's Server
EOF

# 7. Finalize Permissions
# Ensure the 'minecraft' user owns the files we just created
echo "Fixing permissions..."
chown -R minecraft:minecraft "$MC_DIR"

# 8. Mark Initialization as Complete
touch "$FLAG_FILE"
echo "Initialization Complete. Starting Server..."
