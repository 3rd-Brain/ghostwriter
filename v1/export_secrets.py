
import os

def export_secrets_to_env_file():
    # Get all environment variables
    env_vars = os.environ
    
    # Open a .env file for writing
    with open('.env', 'w') as f:
        # Write each environment variable to the file
        for key, value in env_vars.items():
            # Only include relevant secrets, not system variables
            if any(secret_prefix in key for secret_prefix in [
                'ASTRA_DB', 'OPENAI', 'ANTHROPIC', 'AIRTABLE', 
                'API_KEY', 'TOKEN', 'SECRET'
            ]):
                f.write(f'{key}={value}\n')
    
    print("Secrets exported to .env file")

if __name__ == "__main__":
    export_secrets_to_env_file()
