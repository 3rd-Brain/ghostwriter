
#!/usr/bin/env python3
"""
Pricing Configuration Manager
Interactive script to manage pricing_config.json
"""

import json
import os
from typing import Dict, List

class PricingConfigManager:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credit_system', 'pricing_config.json')
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load the pricing configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Config file not found at: {self.config_path}")
            exit(1)
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON in config file: {self.config_path}")
            exit(1)
    
    def save_config(self):
        """Save the configuration back to JSON file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            print("✅ Configuration saved successfully!")
        except Exception as e:
            print(f"❌ Error saving configuration: {str(e)}")
    
    def display_models(self) -> List[str]:
        """Display all models with numbers and return model list"""
        models = list(self.config['models'].keys())
        print("\n📋 Current Models:")
        print("-" * 50)
        for i, model in enumerate(models, 1):
            model_info = self.config['models'][model]
            status_emoji = "🟢" if model_info['status'] == 'active' else "🔴"
            print(f"{i:2d}. {status_emoji} {model}")
            print(f"     Provider: {model_info['provider']}")
            print(f"     Input: ${model_info['input_cost_per_1M_tokens']}/1M tokens")
            print(f"     Output: ${model_info['output_cost_per_1M_tokens']}/1M tokens")
            print()
        return models
    
    def mode_1_add_model(self):
        """Mode 1: Add a new model"""
        print("\n🆕 Adding New Model")
        print("=" * 30)
        
        model_code = input("Enter model code (e.g., 'claude-3-5-sonnet-20241022'): ").strip()
        if not model_code:
            print("❌ Model code cannot be empty")
            return
        
        if model_code in self.config['models']:
            print(f"❌ Model '{model_code}' already exists")
            return
        
        provider = input("Enter provider (e.g., 'anthropic', 'openai'): ").strip().lower()
        if not provider:
            print("❌ Provider cannot be empty")
            return
        
        try:
            input_cost = float(input("Enter input cost per 1M tokens (e.g., 3.0): ").strip())
            output_cost = float(input("Enter output cost per 1M tokens (e.g., 15.0): ").strip())
        except ValueError:
            print("❌ Costs must be valid numbers")
            return
        
        # Add the new model
        self.config['models'][model_code] = {
            "provider": provider,
            "input_cost_per_1M_tokens": input_cost,
            "output_cost_per_1M_tokens": output_cost,
            "status": "active"
        }
        
        print(f"\n✅ Model '{model_code}' added successfully!")
        self.save_config()
    
    def mode_2_deactivate_model(self):
        """Mode 2: Deactivate a model"""
        print("\n🔴 Deactivate Model")
        print("=" * 25)
        
        models = self.display_models()
        if not models:
            print("❌ No models found")
            return
        
        try:
            choice = int(input("Enter the number of the model to deactivate: ").strip())
            if choice < 1 or choice > len(models):
                print("❌ Invalid selection")
                return
            
            selected_model = models[choice - 1]
            self.config['models'][selected_model]['status'] = 'inactive'
            
            print(f"\n✅ Model '{selected_model}' deactivated!")
            self.save_config()
            
        except ValueError:
            print("❌ Please enter a valid number")
    
    def mode_3_update_pricing_settings(self):
        """Mode 3: Update pricing settings"""
        print("\n⚙️  Update Pricing Settings")
        print("=" * 35)
        
        current_markup = self.config['pricing_settings']['markup_percentage']
        current_minimum = self.config['pricing_settings']['minimum_charge']
        
        print(f"Current markup percentage: {current_markup}")
        markup_input = input("Enter new markup percentage (or 'keep' to maintain current): ").strip()
        
        if markup_input.lower() != 'keep':
            try:
                new_markup = float(markup_input)
                self.config['pricing_settings']['markup_percentage'] = new_markup
                print(f"✅ Markup percentage updated to: {new_markup}")
            except ValueError:
                print("❌ Invalid markup percentage, keeping current value")
        
        print(f"\nCurrent minimum charge: {current_minimum}")
        minimum_input = input("Enter new minimum charge (or 'keep' to maintain current): ").strip()
        
        if minimum_input.lower() != 'keep':
            try:
                new_minimum = float(minimum_input)
                self.config['pricing_settings']['minimum_charge'] = new_minimum
                print(f"✅ Minimum charge updated to: {new_minimum}")
            except ValueError:
                print("❌ Invalid minimum charge, keeping current value")
        
        # Update last_updated date
        from datetime import datetime
        self.config['pricing_settings']['last_updated'] = datetime.now().strftime("%Y-%m-%d")
        
        self.save_config()
    
    def mode_4_update_model_pricing(self):
        """Mode 4: Update model pricing"""
        print("\n💰 Update Model Pricing")
        print("=" * 30)
        
        models = self.display_models()
        if not models:
            print("❌ No models found")
            return
        
        try:
            choice = int(input("Enter the number of the model to update: ").strip())
            if choice < 1 or choice > len(models):
                print("❌ Invalid selection")
                return
            
            selected_model = models[choice - 1]
            model_info = self.config['models'][selected_model]
            
            print(f"\nUpdating pricing for: {selected_model}")
            print(f"Current input cost: ${model_info['input_cost_per_1M_tokens']}/1M tokens")
            print(f"Current output cost: ${model_info['output_cost_per_1M_tokens']}/1M tokens")
            
            try:
                new_input_cost = float(input("Enter new input cost per 1M tokens: ").strip())
                new_output_cost = float(input("Enter new output cost per 1M tokens: ").strip())
                
                self.config['models'][selected_model]['input_cost_per_1M_tokens'] = new_input_cost
                self.config['models'][selected_model]['output_cost_per_1M_tokens'] = new_output_cost
                
                print(f"\n✅ Pricing updated for '{selected_model}'!")
                self.save_config()
                
            except ValueError:
                print("❌ Costs must be valid numbers")
                
        except ValueError:
            print("❌ Please enter a valid number")
    
    def mode_5_view_config(self):
        """Mode 5: View current configuration"""
        print("\n📊 Current Configuration")
        print("=" * 35)
        
        # Display models
        self.display_models()
        
        # Display pricing settings
        print("💰 Pricing Settings:")
        print("-" * 20)
        settings = self.config['pricing_settings']
        print(f"Markup Percentage: {settings['markup_percentage']} ({settings['markup_percentage']*100}%)")
        print(f"Minimum Charge: ${settings['minimum_charge']}")
        print(f"Currency: {settings['currency']}")
        print(f"Last Updated: {settings['last_updated']}")
        print()
    
    def run(self):
        """Main interactive loop"""
        while True:
            print("\n" + "="*50)
            print("🔧 PRICING CONFIGURATION MANAGER")
            print("="*50)
            print("1. 🆕 Add New Model")
            print("2. 🔴 Deactivate Model")
            print("3. ⚙️  Update Pricing Settings")
            print("4. 💰 Update Model Pricing")
            print("5. 📊 View Current Configuration")
            print("6. 🚪 Exit")
            print()
            
            choice = input("Select an option (1-6): ").strip()
            
            if choice == '1':
                self.mode_1_add_model()
            elif choice == '2':
                self.mode_2_deactivate_model()
            elif choice == '3':
                self.mode_3_update_pricing_settings()
            elif choice == '4':
                self.mode_4_update_model_pricing()
            elif choice == '5':
                self.mode_5_view_config()
            elif choice == '6':
                print("\n👋 Goodbye!")
                break
            else:
                print("❌ Invalid option. Please choose 1-6.")


if __name__ == "__main__":
    manager = PricingConfigManager()
    manager.run()
