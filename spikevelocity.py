import paramiko
import toml
import os

# Connection details for your Velocity LXC
VELOCITY_HOST = "10.0.0.37" # Internal IP of your Velocity container
SSH_USER = "root"
SSH_PASS = os.environ.get('SSH_PASS')
CONFIG_PATH = "/root/velocity-proxy/velocity.toml"

def add_server_to_velocity(server_name, internal_ip):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(VELOCITY_HOST, username=SSH_USER, password=SSH_PASS)
        sftp = ssh.open_sftp()
        
        # 1. READ AND DECODE
        with sftp.file(CONFIG_PATH, 'r') as f:
            raw_data = f.read()  # This is 'bytes'
            # Convert bytes to string to avoid "Expecting something like a string" error
            config_string = raw_data.decode('utf-8') 
            config = toml.loads(config_string)

        # 2. UPDATE CONFIG
        config['servers'][server_name] = f"{internal_ip}:25565"
        
        full_domain = f"{server_name}.spikenet.net"
        if 'forced-hosts' not in config:
            config['forced-hosts'] = {}
        config['forced-hosts'][full_domain] = [server_name]

        # 3. CONVERT BACK TO STRING AND WRITE
        new_toml_string = toml.dumps(config)
        with sftp.file(CONFIG_PATH, 'w') as f:
            f.write(new_toml_string)
        
        # 4. RELOAD
        ssh.exec_command('pkill -SIGHUP -f velocity.jar')
        
        print(f"Velocity updated for {server_name}")
        return True

    except Exception as e:
        print(f"Velocity Update Error: {e}")
        return False
    finally:
        ssh.close()

def remove_server_from_velocity(server_name):
    """
    Removes the server entry and its associated forced-host from velocity.toml
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(VELOCITY_HOST, username=SSH_USER, password=SSH_PASS)
        sftp = ssh.open_sftp()
        
        # 1. READ AND DECODE
        with sftp.file(CONFIG_PATH, 'r') as f:
            raw_data = f.read()
            config_string = raw_data.decode('utf-8')
            config = toml.loads(config_string)

        # 2. REMOVE ENTRIES
        # Remove from [servers] section
        if 'servers' in config:
            config['servers'].pop(server_name, None)
            print(f"Removed {server_name} from [servers]")
        
        # Remove from [forced-hosts] section
        full_domain = f"{server_name}.spikenet.net"
        if 'forced-hosts' in config:
            config['forced-hosts'].pop(full_domain, None)
            print(f"Removed {full_domain} from [forced-hosts]")

        # 3. CONVERT BACK TO TOML AND WRITE
        new_toml_string = toml.dumps(config)
        with sftp.file(CONFIG_PATH, 'w') as f:
            f.write(new_toml_string)
        
        # 4. RELOAD
        # This ensures the proxy updates its internal memory
        ssh.exec_command('pkill -SIGHUP -f velocity.jar')
        
        print(f"Velocity cleanup complete for {server_name}")
        return True

    except Exception as e:
        print(f"Velocity Removal Error: {e}")
        return False
    finally:
        ssh.close()