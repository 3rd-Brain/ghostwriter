#!/usr/bin/env python3
"""
Credit System Tester - Interactive testing script for credit system functionality

This script provides an interactive menu to test various credit system processes:
- Buy Credits (Purchase simulation)
- Generate with Workflow (Full generation process simulation)
- Check User Balance
- View Transaction History
- Reserve/Release Credits
- Add Bonus Credits
- Process Refund
- Bulk User Testing
- Cost Estimation Testing

Usage: python admin_scripts/credit_system_tester.py
"""

import sys
import os
import json
import uuid
from datetime import datetime
from typing import Dict, List

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from credit_system.credit_manager import CreditManager
from credit_system.credit_transaction_logger import CreditTransactionLogger
from credit_system.credit_database_manager import CreditDatabaseManager

class CreditSystemTester:
    def __init__(self):
        try:
            self.credit_manager = CreditManager()
            self.transaction_logger = CreditTransactionLogger()
            self.db_manager = CreditDatabaseManager()
            print("✅ Credit system modules loaded successfully!")
        except Exception as e:
            print(f"❌ Error initializing credit system: {str(e)}")
            print("Make sure your database connections are configured properly.")
            sys.exit(1)

    def display_menu(self):
        """Display the main menu options"""
        print("\n" + "="*60)
        print("🧪 CREDIT SYSTEM TESTER")
        print("="*60)
        print("1.  💳 Buy Credits (Purchase Simulation)")
        print("2.  🤖 Generate with Workflow (Full Process)")
        print("3.  💰 Check User Balance")
        print("4.  📋 View Transaction History")
        print("5.  🔒 Reserve Credits")
        print("6.  🔓 Release Reserved Credits")
        print("7.  🎁 Add Bonus Credits")
        print("8.  💸 Process Refund")
        print("9.  📊 Get User Credit Summary")
        print("10. 💡 Cost Estimation Testing")
        print("11. 👥 Bulk User Testing")
        print("12. 🔍 Validate Credit Operations")
        print("13. 📈 Transaction Analytics")
        print("14. 🔬 Real Workflow Generation with Token Tracking")
        print("0.  🚪 Exit")
        print("="*60)

    def get_user_input(self, prompt: str, default: str = None) -> str:
        """Get user input with optional default value"""
        if default:
            response = input(f"{prompt} [{default}]: ").strip()
            return response if response else default
        return input(f"{prompt}: ").strip()

    def test_buy_credits(self):
        """Test credit purchase process"""
        print("\n💳 CREDIT PURCHASE SIMULATION")
        print("-" * 40)

        user_id = self.get_user_input("Enter User ID", "test_user_123")

        try:
            amount = float(self.get_user_input("Enter credit amount to purchase", "10.0"))
            payment_amount = float(self.get_user_input("Enter payment amount (USD)", str(amount)))
        except ValueError:
            print("❌ Invalid amount entered")
            return

        payment_method = self.get_user_input("Payment method", "test_payment")

        purchase_details = {
            "payment_id": f"pay_{uuid.uuid4().hex[:8]}",
            "payment_method": payment_method,
            "payment_amount": payment_amount,
            "currency": "USD",
            "purchase_package": f"{amount} credits"
        }

        try:
            print(f"\n🔄 Processing purchase of {amount} credits for user {user_id}...")
            transaction_id = self.transaction_logger.log_credit_purchase(
                user_id, amount, purchase_details
            )

            print(f"✅ Purchase successful!")
            print(f"   Transaction ID: {transaction_id}")
            print(f"   Credits added: {amount}")
            print(f"   New balance: {self.credit_manager.get_user_credit_balance(user_id)}")

        except Exception as e:
            print(f"❌ Purchase failed: {str(e)}")

    def test_workflow_generation(self):
        """Test full workflow generation process with credit deduction"""
        print("\n🤖 WORKFLOW GENERATION SIMULATION")
        print("-" * 40)

        user_id = self.get_user_input("Enter User ID", "test_user_123")
        workflow_name = self.get_user_input("Workflow name", "Standard Short-Form Flow")
        content_length = int(self.get_user_input("Estimated content length (characters)", "500"))
        model_name = self.get_user_input("Model to use", "gpt-4o-mini")

        try:
            # Step 1: Estimate cost
            estimated_cost = self.credit_manager.estimate_generation_cost(
                workflow_name, content_length, model_name
            )
            print(f"\n📊 Estimated cost: ${estimated_cost:.6f}")

            # Step 2: Validate user has sufficient credits
            has_credits = self.credit_manager.validate_user_credits(user_id, estimated_cost)
            current_balance = self.credit_manager.get_user_credit_balance(user_id)

            print(f"💰 Current balance: ${current_balance:.6f}")
            print(f"✅ Sufficient credits: {has_credits}")

            if not has_credits:
                print("❌ Insufficient credits for this operation")
                return

            # Step 3: Reserve credits
            print(f"\n🔒 Reserving {estimated_cost:.6f} credits...")
            reserved = self.credit_manager.reserve_credits(user_id, estimated_cost)

            if not reserved:
                print("❌ Failed to reserve credits")
                return

            print("✅ Credits reserved successfully")

            # Step 4: Simulate generation (fake token usage)
            print("\n🤖 Simulating generation process...")

            # Simulate some token usage based on content length
            input_tokens = int(content_length * 0.25)  # ~4 chars per token
            output_tokens = int(input_tokens * 0.6)    # Assume 60% output ratio

            tokens_used = {
                "input": input_tokens,
                "output": output_tokens
            }

            print(f"📝 Simulated tokens used: {input_tokens} input, {output_tokens} output")

            # Step 5: Calculate actual cost
            actual_cost = self.credit_manager.calculate_actual_cost(tokens_used, model_name)
            print(f"💵 Actual cost: ${actual_cost:.6f}")

            # Step 6: Deduct credits and log transaction
            operation_details = {
                "operation_id": f"gen_{uuid.uuid4().hex[:8]}",
                "operation_type": "content_generation",
                "workflow_name": workflow_name,
                "tokens_used": tokens_used,
                "model_used": model_name,
                "actual_cost": actual_cost,
                "estimated_cost": estimated_cost,
                "reserved_amount": estimated_cost
            }

            print(f"\n💸 Deducting {actual_cost:.6f} credits...")
            deduction_result = self.credit_manager.deduct_credits(
                user_id, actual_cost, operation_details
            )

            if deduction_result["status"] == "success":
                print("✅ Generation process completed successfully!")
                print(f"   Transaction ID: {deduction_result['transaction_id']}")
                print(f"   Amount deducted: ${deduction_result['amount_deducted']:.6f}")
                print(f"   New balance: ${deduction_result['new_balance']:.6f}")
            else:
                print(f"❌ Deduction failed: {deduction_result['message']}")
                # Release reserved credits on failure
                self.credit_manager.release_reserved_credits(user_id, estimated_cost)
                print("🔓 Reserved credits released due to failure")

        except Exception as e:
            print(f"❌ Generation process failed: {str(e)}")
            # Try to release any reserved credits
            try:
                self.credit_manager.release_reserved_credits(user_id, estimated_cost)
                print("🔓 Reserved credits released due to error")
            except:
                pass

    def test_check_balance(self):
        """Test checking user balance"""
        print("\n💰 CHECK USER BALANCE")
        print("-" * 40)

        user_id = self.get_user_input("Enter User ID", "test_user_123")

        try:
            balance = self.credit_manager.get_user_credit_balance(user_id)
            print(f"💰 Current balance for {user_id}: ${balance:.6f}")

            # Get full credit info
            credit_info = self.db_manager.get_user_credit_info(user_id)
            if credit_info["status"] == "success":
                credits = credit_info["credits"]
                print(f"📊 Credit Details:")
                print(f"   Total purchased: ${credits.get('total_purchased', 0):.6f}")
                print(f"   Total consumed: ${credits.get('total_consumed', 0):.6f}")
                print(f"   Reserved credits: ${credits.get('reserved_credits', 0):.6f}")
                print(f"   Last update: {credits.get('last_credit_update', 'N/A')}")

        except Exception as e:
            print(f"❌ Error checking balance: {str(e)}")

    def test_transaction_history(self):
        """Test viewing transaction history"""
        print("\n📋 TRANSACTION HISTORY")
        print("-" * 40)

        user_id = self.get_user_input("Enter User ID", "test_user_123")
        limit = int(self.get_user_input("Number of transactions to show", "10"))

        try:
            transactions = self.transaction_logger.get_user_transaction_history(user_id, limit)

            if not transactions:
                print(f"📭 No transactions found for user {user_id}")
                return

            print(f"\n📋 Last {len(transactions)} transactions for {user_id}:")
            print("-" * 80)

            for i, tx in enumerate(transactions, 1):
                amount = float(tx['amount'])
                amount_str = f"+${abs(amount):.6f}" if amount >= 0 else f"-${abs(amount):.6f}"

                print(f"{i:2d}. [{tx['type'].upper()}] {amount_str}")
                print(f"    ID: {tx['transaction_id']}")
                print(f"    Balance: ${tx['balance_before']:.6f} → ${tx['balance_after']:.6f}")
                print(f"    Date: {tx['created_at']}")
                if tx.get('metadata'):
                    print(f"    Metadata: {json.dumps(tx['metadata'], indent=6)}")
                print()

        except Exception as e:
            print(f"❌ Error retrieving transaction history: {str(e)}")

    def test_reserve_credits(self):
        """Test credit reservation"""
        print("\n🔒 RESERVE CREDITS")
        print("-" * 40)

        user_id = self.get_user_input("Enter User ID", "test_user_123")

        try:
            amount = float(self.get_user_input("Amount to reserve", "1.0"))
        except ValueError:
            print("❌ Invalid amount entered")
            return

        try:
            current_balance = self.credit_manager.get_user_credit_balance(user_id)
            print(f"💰 Current balance: ${current_balance:.6f}")

            success = self.credit_manager.reserve_credits(user_id, amount)

            if success:
                print(f"✅ Successfully reserved ${amount:.6f} credits")
                # Check updated info
                credit_info = self.db_manager.get_user_credit_info(user_id)
                if credit_info["status"] == "success":
                    reserved = credit_info["credits"].get("reserved_credits", 0)
                    print(f"🔒 Total reserved credits: ${reserved:.6f}")
            else:
                print("❌ Failed to reserve credits (insufficient balance?)")

        except Exception as e:
            print(f"❌ Error reserving credits: {str(e)}")

    def test_release_credits(self):
        """Test releasing reserved credits"""
        print("\n🔓 RELEASE RESERVED CREDITS")
        print("-" * 40)

        user_id = self.get_user_input("Enter User ID", "test_user_123")

        try:
            # Show current reserved amount
            credit_info = self.db_manager.get_user_credit_info(user_id)
            if credit_info["status"] == "success":
                reserved = credit_info["credits"].get("reserved_credits", 0)
                print(f"🔒 Currently reserved: ${reserved:.6f}")

            amount = float(self.get_user_input("Amount to release", str(reserved)))
        except ValueError:
            print("❌ Invalid amount entered")
            return
        except Exception as e:
            print(f"❌ Error getting reserved credits: {str(e)}")
            return

        try:
            success = self.credit_manager.release_reserved_credits(user_id, amount)

            if success:
                print(f"✅ Successfully released ${amount:.6f} credits")
                # Check updated info
                credit_info = self.db_manager.get_user_credit_info(user_id)
                if credit_info["status"] == "success":
                    reserved = credit_info["credits"].get("reserved_credits", 0)
                    print(f"🔒 Remaining reserved credits: ${reserved:.6f}")
            else:
                print("❌ Failed to release credits")

        except Exception as e:
            print(f"❌ Error releasing credits: {str(e)}")

    def test_bonus_credits(self):
        """Test adding bonus credits"""
        print("\n🎁 ADD BONUS CREDITS")
        print("-" * 40)

        user_id = self.get_user_input("Enter User ID", "test_user_123")

        try:
            amount = float(self.get_user_input("Bonus amount", "5.0"))
        except ValueError:
            print("❌ Invalid amount entered")
            return

        bonus_type = self.get_user_input("Bonus type", "manual_bonus")
        reason = self.get_user_input("Reason for bonus", "Testing bonus system")
        admin_user = self.get_user_input("Admin user", "admin_tester")

        bonus_details = {
            "bonus_id": f"bonus_{uuid.uuid4().hex[:8]}",
            "bonus_type": bonus_type,
            "reason": reason,
            "admin_user": admin_user
        }

        try:
            current_balance = self.credit_manager.get_user_credit_balance(user_id)
            print(f"💰 Current balance: ${current_balance:.6f}")

            transaction_id = self.transaction_logger.log_credit_bonus(
                user_id, amount, bonus_details
            )

            new_balance = self.credit_manager.get_user_credit_balance(user_id)

            print(f"✅ Bonus added successfully!")
            print(f"   Transaction ID: {transaction_id}")
            print(f"   Bonus amount: +${amount:.6f}")
            print(f"   New balance: ${new_balance:.6f}")

        except Exception as e:
            print(f"❌ Error adding bonus: {str(e)}")

    def test_refund(self):
        """Test processing a refund"""
        print("\n💸 PROCESS REFUND")
        print("-" * 40)

        user_id = self.get_user_input("Enter User ID", "test_user_123")

        try:
            amount = float(self.get_user_input("Refund amount", "2.0"))
        except ValueError:
            print("❌ Invalid amount entered")
            return

        original_tx = self.get_user_input("Original transaction ID (optional)", "")
        reason = self.get_user_input("Refund reason", "Testing refund system")
        admin_user = self.get_user_input("Admin user", "admin_tester")

        refund_details = {
            "refund_id": f"refund_{uuid.uuid4().hex[:8]}",
            "original_transaction_id": original_tx if original_tx else None,
            "refund_reason": reason,
            "admin_user": admin_user
        }

        try:
            current_balance = self.credit_manager.get_user_credit_balance(user_id)
            print(f"💰 Current balance: ${current_balance:.6f}")

            transaction_id = self.transaction_logger.log_credit_refund(
                user_id, amount, refund_details
            )

            new_balance = self.credit_manager.get_user_credit_balance(user_id)

            print(f"✅ Refund processed successfully!")
            print(f"   Transaction ID: {transaction_id}")
            print(f"   Refund amount: +${amount:.6f}")
            print(f"   New balance: ${new_balance:.6f}")

        except Exception as e:
            print(f"❌ Error processing refund: {str(e)}")

    def test_user_summary(self):
        """Test getting comprehensive user credit summary"""
        print("\n📊 USER CREDIT SUMMARY")
        print("-" * 40)

        user_id = self.get_user_input("Enter User ID", "test_user_123")

        try:
            summary = self.credit_manager.get_user_credit_summary(user_id)

            if summary["status"] == "success":
                print(f"📊 Credit Summary for {user_id}:")
                print(f"   Current Balance: ${summary['current_balance']:.6f}")
                print(f"   Total Purchased: ${summary['total_purchased']:.6f}")
                print(f"   Total Consumed: ${summary['total_consumed']:.6f}")
                print(f"   Reserved Credits: ${summary['reserved_credits']:.6f}")
                print(f"   Last Update: {summary['last_credit_update']}")

                tx_summary = summary.get('transaction_summary', {})
                print(f"\n📈 Transaction Summary:")
                print(f"   Total Transactions: {tx_summary.get('total_transactions', 0)}")
                print(f"   Total Purchased: ${tx_summary.get('total_purchased', 0):.6f}")
                print(f"   Total Consumed: ${tx_summary.get('total_consumed', 0):.6f}")
                print(f"   Total Refunded: ${tx_summary.get('total_refunded', 0):.6f}")
                print(f"   Total Bonus: ${tx_summary.get('total_bonus', 0):.6f}")

            else:
                print(f"❌ Error getting summary: {summary['message']}")

        except Exception as e:
            print(f"❌ Error getting user summary: {str(e)}")

    def test_cost_estimation(self):
        """Test cost estimation functions"""
        print("\n💡 COST ESTIMATION TESTING")
        print("-" * 40)

        workflow_name = self.get_user_input("Workflow name", "Standard Short-Form Flow")
        content_length = int(self.get_user_input("Content length (characters)", "1000"))

        print("\n🧮 Testing cost estimation for different models:")
        print("-" * 50)

        models = list(self.credit_manager.pricing_config["models"].keys())

        for model in models:
            try:
                estimated_cost = self.credit_manager.estimate_generation_cost(
                    workflow_name, content_length, model
                )
                print(f"   {model}: ${estimated_cost:.6f}")
            except Exception as e:
                print(f"   {model}: Error - {str(e)}")

        # Test actual cost calculation
        print(f"\n🔢 Testing actual cost calculation:")
        print("-" * 50)

        tokens_used = {
            "input": int(content_length * 0.25),
            "output": int(content_length * 0.25 * 0.6)
        }

        print(f"Simulated tokens: {tokens_used['input']} input, {tokens_used['output']} output")

        for model in models:
            try:
                actual_cost = self.credit_manager.calculate_actual_cost(tokens_used, model)
                print(f"   {model}: ${actual_cost:.6f}")
            except Exception as e:
                print(f"   {model}: Error - {str(e)}")

    def test_bulk_users(self):
        """Test operations on multiple users"""
        print("\n👥 BULK USER TESTING")
        print("-" * 40)

        base_user_id = self.get_user_input("Base user ID", "bulk_test_user")
        num_users = int(self.get_user_input("Number of users to test", "3"))

        users = [f"{base_user_id}_{i+1}" for i in range(num_users)]

        print(f"\n🔄 Testing with users: {', '.join(users)}")

        # Give each user some initial credits
        print("\n💳 Adding initial credits to all users...")
        for user in users:
            try:
                purchase_details = {
                    "payment_id": f"bulk_pay_{uuid.uuid4().hex[:8]}",
                    "payment_method": "bulk_test",
                    "payment_amount": 10.0,
                    "currency": "USD",
                    "purchase_package": "10 credits bulk test"
                }

                transaction_id = self.transaction_logger.log_credit_purchase(
                    user, 10.0, purchase_details
                )

                balance = self.credit_manager.get_user_credit_balance(user)
                print(f"   ✅ {user}: ${balance:.6f}")

            except Exception as e:
                print(f"   ❌ {user}: Error - {str(e)}")

        # Test workflow generation for all users
        print(f"\n🤖 Running workflow generation for all users...")
        for user in users:
            try:
                # Simulate a small generation
                estimated_cost = self.credit_manager.estimate_generation_cost(
                    "Test Workflow", 200, "gpt-4o-mini"
                )

                if self.credit_manager.validate_user_credits(user, estimated_cost):
                    # Simulate generation process
                    tokens_used = {"input": 50, "output": 30}
                    actual_cost = self.credit_manager.calculate_actual_cost(tokens_used, "gpt-4o-mini")

                    operation_details = {
                        "operation_id": f"bulk_gen_{uuid.uuid4().hex[:8]}",
                        "operation_type": "bulk_test_generation",
                        "workflow_name": "Bulk Test Workflow",
                        "tokens_used": tokens_used,
                        "model_used": "gpt-4o-mini",
                        "actual_cost": actual_cost,
                        "estimated_cost": estimated_cost
                    }

                    result = self.credit_manager.deduct_credits(user, actual_cost, operation_details)

                    if result["status"] == "success":
                        print(f"   ✅ {user}: Generation completed, balance: ${result['new_balance']:.6f}")
                    else:
                        print(f"   ❌ {user}: Generation failed - {result['message']}")
                else:
                    balance = self.credit_manager.get_user_credit_balance(user)
                    print(f"   ⚠️  {user}: Insufficient credits (${balance:.6f} < ${estimated_cost:.6f})")

            except Exception as e:
                print(f"   ❌ {user}: Error - {str(e)}")

    def test_validate_operations(self):
        """Test credit validation operations"""
        print("\n🔍 VALIDATE CREDIT OPERATIONS")
        print("-" * 40)

        user_id = self.get_user_input("Enter User ID", "test_user_123")

        try:
            # Test various validation scenarios
            test_amounts = [0.001, 0.01, 0.1, 1.0, 10.0, 100.0]
            current_balance = self.credit_manager.get_user_credit_balance(user_id)

            print(f"💰 Current balance: ${current_balance:.6f}")
            print(f"\n🧪 Testing validation for different amounts:")
            print("-" * 50)

            for amount in test_amounts:
                is_valid = self.credit_manager.validate_user_credits(user_id, amount)
                status = "✅ VALID" if is_valid else "❌ INVALID"
                print(f"   ${amount:.3f}: {status}")

            # Test edge cases
            print(f"\n🔬 Testing edge cases:")
            print("-" * 50)

            # Test with exact balance
            is_valid = self.credit_manager.validate_user_credits(user_id, current_balance)
            status = "✅ VALID" if is_valid else "❌ INVALID"
            print(f"   Exact balance (${current_balance:.6f}): {status}")

            # Test with slightly more than balance
            is_valid = self.credit_manager.validate_user_credits(user_id, current_balance + 0.000001)
            status = "✅ VALID" if is_valid else "❌ INVALID"
            print(f"   Slightly over balance: {status}")

        except Exception as e:
            print(f"❌ Error during validation testing: {str(e)}")

    def test_transaction_analytics(self):
        """Test transaction analytics and reporting"""
        print("\n📈 TRANSACTION ANALYTICS")
        print("-" * 40)

        user_id = self.get_user_input("Enter User ID", "test_user_123")

        try:
            # Get transaction summary
            summary = self.transaction_logger.get_user_transaction_summary(user_id)

            print(f"📊 Transaction Analytics for {user_id}:")
            print(f"   Total Transactions: {summary['total_transactions']}")
            print(f"   Total Value Flow:")
            print(f"     📈 Purchased: +${summary['total_purchased']:.6f}")
            print(f"     📉 Consumed: -${summary['total_consumed']:.6f}")
            print(f"     🎁 Bonus: +${summary['total_bonus']:.6f}")
            print(f"     💸 Refunded: +${summary['total_refunded']:.6f}")

            net_flow = (summary['total_purchased'] + summary['total_bonus'] + 
                       summary['total_refunded'] - summary['total_consumed'])
            print(f"     💰 Net Flow: {'+' if net_flow >= 0 else ''}${net_flow:.6f}")

            if summary['last_transaction']:
                last_tx = summary['last_transaction']
                print(f"\n📋 Last Transaction:")
                print(f"     Type: {last_tx['type'].upper()}")
                print(f"     Amount: ${float(last_tx['amount']):.6f}")
                print(f"     Date: {last_tx['created_at']}")

            # Get recent transactions by type
            all_transactions = self.transaction_logger.get_user_transaction_history(user_id, 100)

            if all_transactions:
                print(f"\n📊 Transaction Breakdown:")
                types = {}
                for tx in all_transactions:
                    tx_type = tx['type']
                    if tx_type not in types:
                        types[tx_type] = {'count': 0, 'amount': 0.0}
                    types[tx_type]['count'] += 1
                    types[tx_type]['amount'] += abs(float(tx['amount']))

                for tx_type, data in types.items():
                    emoji = {'purchase': '💳', 'consumption': '🤖', 'bonus': '🎁', 'refund': '💸'}.get(tx_type, '📄')
                    print(f"     {emoji} {tx_type.title()}: {data['count']} transactions, ${data['amount']:.6f}")

        except Exception as e:
            print(f"❌ Error generating analytics: {str(e)}")

    def test_real_workflow_generation(self):
        """Test real workflow generation with token tracking"""
        print("\n🔬 REAL WORKFLOW GENERATION WITH TOKEN TRACKING")
        print("-" * 60)

        # Get workflow name
        workflow_name = self.get_user_input("Workflow name", "Standard Short-Form Flow")

        # Get topic for content generation
        topic = self.get_user_input("Content topic", "digital marketing strategy")

        # Get brand name
        brand_name = self.get_user_input("Brand name", "Test Brand")

        # Get number of posts to generate
        try:
            num_posts = int(self.get_user_input("Number of posts to generate", "3"))
        except ValueError:
            print("❌ Invalid number entered, using default of 3")
            num_posts = 3

        print(f"\n🔄 Starting real generation process...")
        print(f"Workflow: {workflow_name}")
        print(f"Topic: {topic}")
        print(f"Brand: {brand_name}")
        print(f"Number of posts: {num_posts}")

        try:
            # Get user ID from environment
            user_id = os.environ.get("CURRENT_USER_ID", "test_user_123")
            os.environ["CURRENT_USER_ID"] = user_id

            # Import required modules
            from social_writer import source_content_retriever, multitemplate_retriever, get_client_brand_voice
            from social_dynamic_generation_flow import flow_config_retriever, social_post_generation_with_json
            from third_party_keys import get_third_party_key
            import anthropic

            # Get API client
            user_api_key = get_third_party_key(user_id, "anthropic")
            if not user_api_key:
                print("❌ No Anthropic API key found for user. Please add your API key in settings.")
                return

            anthropic_client = anthropic.Client(api_key=user_api_key)

            # Step 1: Get source content
            print("\n📖 Retrieving source content...")
            source_results = source_content_retriever(topic)
            content_chunks = []
            if source_results.get("data", {}).get("documents"):
                content_chunks = [doc["content"] for doc in source_results["data"]["documents"][:3]]

            if not content_chunks:
                print("⚠️ No source content found, using default content")
                combined_chunks = f"Sample content about {topic} and best practices for digital marketing engagement."
            else:
                combined_chunks = "\n\n".join(content_chunks)

            # Step 2: Get templates
            print("📋 Retrieving templates...")
            template_results = multitemplate_retriever(combined_chunks, template_count_to_retrieve=num_posts)

            if not template_results.get("data", {}).get("documents"):
                print("❌ No templates found for generation")
                return

            templates = template_results["data"]["documents"][:num_posts]

            # Step 3: Get brand voice
            print("🎨 Retrieving brand voice...")
            try:
                brand_voice_result = get_client_brand_voice(brand_name, user_id)
                brand_voice = brand_voice_result["brand_voice"]
            except:
                brand_voice = "Professional, engaging, and informative tone."
                print(f"⚠️ Using default brand voice: {brand_voice}")

            # Step 4: Get workflow configuration
            print("⚙️ Retrieving workflow configuration...")
            flow_config = flow_config_retriever(workflow_name)
            steps = sorted(flow_config["steps"], key=lambda x: x["Order"])

            print(f"✅ Found workflow with {len(steps)} steps")

            # Step 5: Generate content for each template with token tracking
            all_generations = []
            total_cost_all = 0.0

            for post_num, template in enumerate(templates, 1):
                print(f"\n{'='*50}")
                print(f"🤖 GENERATING POST {post_num}/{len(templates)}")
                print(f"{'='*50}")

                template_content = template.get("template", template.get("content", ""))
                print(f"Template: {template_content[:100]}...")

                # Track generation for this post
                generation_data = {
                    "post_number": post_num,
                    "template": template_content,
                    "steps": [],
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cost": 0.0,
                    "final_content": ""
                }

                prev_output = ""

                # Process each step with token tracking
                for step_num, step in enumerate(steps, 1):
                    print(f"\n--- Step {step_num}: {step['Step_name']} ---")

                    # Prepare messages
                    messages = []
                    for msg in step["Message"]: