
import os
import json
import asyncio
import statistics
from typing import Dict, List, Tuple
from datetime import datetime
import requests
from social_dynamic_generation_flow import flow_config_retriever, social_post_generation_with_json
from social_writer import get_client_brand_voice, source_content_retriever, multitemplate_retriever
from third_party_keys import get_third_party_key
from openai import OpenAI
import anthropic

class TokenTracker:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.token_usage_log = []
        self.workflow_results = {}
        
        # Get API clients
        self.openai_client = self._get_openai_client()
        self.anthropic_client = self._get_anthropic_client()
        
    def _get_openai_client(self):
        """Get OpenAI client with user API key"""
        user_api_key = get_third_party_key(self.user_id, "openai")
        if not user_api_key:
            raise ValueError("No OpenAI API key found for this user")
        return OpenAI(api_key=user_api_key)
        
    def _get_anthropic_client(self):
        """Get Anthropic client with user API key"""
        user_api_key = get_third_party_key(self.user_id, "anthropic")
        if not user_api_key:
            raise ValueError("No Anthropic API key found for this user")
        return anthropic.Client(api_key=user_api_key)

    def get_system_workflows(self) -> List[str]:
        """Get all system workflow names"""
        ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
        ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
        
        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/sys_keyspace/workflows"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }
        
        payload = {"find": {"filter": {}}}
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        workflows = result.get("data", {}).get("documents", [])
        return [workflow.get("workflow_name", "") for workflow in workflows if workflow.get("workflow_name")]

    def prepare_test_data(self) -> Dict:
        """Prepare test data for generation"""
        print("Preparing test data...")
        
        # Get source content
        source_results = source_content_retriever("digital marketing strategy")
        content_chunks = []
        if source_results.get("data", {}).get("documents"):
            content_chunks = [doc["content"] for doc in source_results["data"]["documents"][:3]]
        
        combined_chunks = "\n\n".join(content_chunks) if content_chunks else "Sample content about digital marketing strategies and best practices for social media engagement."
        
        # Get templates
        template_results = multitemplate_retriever(combined_chunks, template_count_to_retrieve=3)
        template = "Share your thoughts on {topic}. What's your experience with this?"
        if template_results.get("data", {}).get("documents"):
            template = template_results["data"]["documents"][0].get("template", template)
        
        # Get brand voice
        try:
            brand_voice_result = get_client_brand_voice("Test Brand", self.user_id)
            brand_voice = brand_voice_result.get("brand_voice", "Professional, engaging, and informative tone.")
        except:
            brand_voice = "Professional, engaging, and informative tone."
        
        return {
            "content_chunks": combined_chunks,
            "template": template,
            "brand_voice": brand_voice
        }

    def track_anthropic_generation(self, workflow_name: str, test_data: Dict) -> Dict:
        """Generate content and track Anthropic token usage"""
        print(f"\n--- Tracking tokens for workflow: {workflow_name} ---")
        
        try:
            # Get flow configuration
            flow_config = flow_config_retriever(workflow_name)
            steps = sorted(flow_config["steps"], key=lambda x: x["Order"])
            
            step_results = []
            prev_output = ""
            total_input_tokens = 0
            total_output_tokens = 0
            
            for step in steps:
                print(f"Processing step: {step['Step_name']}")
                
                # Prepare messages
                messages = []
                for msg in step["Message"]:
                    template_str = msg["content"].replace('\\n', '\n')
                    content = template_str.format(
                        client_brief=test_data["brand_voice"],
                        template=test_data["template"],
                        content_chunks=test_data["content_chunks"],
                        brand_voice=test_data["brand_voice"],
                        prev_ai_output=prev_output
                    )
                    messages.append({"role": msg["role"], "content": content})
                
                # Make API call and track usage
                response = self.anthropic_client.messages.create(
                    model=step["Model"],
                    system=step["System_prompt"],
                    messages=messages,
                    max_tokens=step["Max_tokens"],
                    temperature=step["Temperature"]
                )
                
                # Extract token usage
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens
                
                step_result = {
                    "step_name": step["Step_name"],
                    "model": step["Model"],
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens
                }
                
                step_results.append(step_result)
                prev_output = response.content[0].text
                
                print(f"  Model: {step['Model']}")
                print(f"  Input tokens: {input_tokens}")
                print(f"  Output tokens: {output_tokens}")
                print(f"  Total tokens: {input_tokens + output_tokens}")
            
            return {
                "workflow_name": workflow_name,
                "steps": step_results,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
                "final_output": prev_output
            }
            
        except Exception as e:
            print(f"Error tracking workflow {workflow_name}: {str(e)}")
            return {
                "workflow_name": workflow_name,
                "error": str(e),
                "steps": [],
                "total_tokens": 0
            }

    def run_workflow_analysis(self, num_runs: int = 5) -> Dict:
        """Run token analysis for all system workflows"""
        print(f"\n=== Starting Token Analysis for System Workflows ===")
        print(f"Number of runs per workflow: {num_runs}")
        
        # Set current user ID for other functions
        os.environ["CURRENT_USER_ID"] = self.user_id
        
        # Get system workflows
        workflows = self.get_system_workflows()
        print(f"Found {len(workflows)} system workflows: {workflows}")
        
        # Prepare test data once
        test_data = self.prepare_test_data()
        print(f"Test data prepared:")
        print(f"  Content chunks length: {len(test_data['content_chunks'])}")
        print(f"  Template: {test_data['template'][:100]}...")
        print(f"  Brand voice: {test_data['brand_voice'][:100]}...")
        
        workflow_stats = {}
        
        for workflow_name in workflows:
            print(f"\n{'='*60}")
            print(f"ANALYZING WORKFLOW: {workflow_name}")
            print(f"{'='*60}")
            
            workflow_runs = []
            
            for run_num in range(1, num_runs + 1):
                print(f"\n--- Run {run_num}/{num_runs} for {workflow_name} ---")
                
                result = self.track_anthropic_generation(workflow_name, test_data)
                
                if "error" not in result:
                    workflow_runs.append(result)
                    print(f"Run {run_num} completed - Total tokens: {result['total_tokens']}")
                else:
                    print(f"Run {run_num} failed: {result['error']}")
            
            if workflow_runs:
                # Calculate statistics
                total_tokens = [run["total_tokens"] for run in workflow_runs]
                input_tokens = [run["total_input_tokens"] for run in workflow_runs]
                output_tokens = [run["total_output_tokens"] for run in workflow_runs]
                
                workflow_stats[workflow_name] = {
                    "successful_runs": len(workflow_runs),
                    "failed_runs": num_runs - len(workflow_runs),
                    "token_stats": {
                        "total_tokens": {
                            "min": min(total_tokens),
                            "max": max(total_tokens),
                            "mean": statistics.mean(total_tokens),
                            "median": statistics.median(total_tokens),
                            "stdev": statistics.stdev(total_tokens) if len(total_tokens) > 1 else 0
                        },
                        "input_tokens": {
                            "min": min(input_tokens),
                            "max": max(input_tokens),
                            "mean": statistics.mean(input_tokens),
                            "median": statistics.median(input_tokens),
                            "stdev": statistics.stdev(input_tokens) if len(input_tokens) > 1 else 0
                        },
                        "output_tokens": {
                            "min": min(output_tokens),
                            "max": max(output_tokens),
                            "mean": statistics.mean(output_tokens),
                            "median": statistics.median(output_tokens),
                            "stdev": statistics.stdev(output_tokens) if len(output_tokens) > 1 else 0
                        }
                    },
                    "step_breakdown": self._analyze_step_breakdown(workflow_runs),
                    "raw_runs": workflow_runs
                }
                
                print(f"\n--- Statistics for {workflow_name} ---")
                print(f"Successful runs: {len(workflow_runs)}/{num_runs}")
                print(f"Average total tokens: {statistics.mean(total_tokens):.1f}")
                print(f"Token range: {min(total_tokens)} - {max(total_tokens)}")
        
        return workflow_stats

    def _analyze_step_breakdown(self, workflow_runs: List[Dict]) -> Dict:
        """Analyze token usage by step across runs"""
        step_stats = {}
        
        for run in workflow_runs:
            for step in run["steps"]:
                step_name = step["step_name"]
                model = step["model"]
                
                if step_name not in step_stats:
                    step_stats[step_name] = {
                        "model": model,
                        "input_tokens": [],
                        "output_tokens": [],
                        "total_tokens": []
                    }
                
                step_stats[step_name]["input_tokens"].append(step["input_tokens"])
                step_stats[step_name]["output_tokens"].append(step["output_tokens"])
                step_stats[step_name]["total_tokens"].append(step["total_tokens"])
        
        # Calculate averages for each step
        for step_name, data in step_stats.items():
            step_stats[step_name]["avg_input_tokens"] = statistics.mean(data["input_tokens"])
            step_stats[step_name]["avg_output_tokens"] = statistics.mean(data["output_tokens"])
            step_stats[step_name]["avg_total_tokens"] = statistics.mean(data["total_tokens"])
        
        return step_stats

    def generate_report(self, workflow_stats: Dict) -> str:
        """Generate a comprehensive report"""
        report = []
        report.append("="*80)
        report.append("TOKEN USAGE ANALYSIS REPORT")
        report.append("="*80)
        report.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"User ID: {self.user_id}")
        report.append("")
        
        report.append("WORKFLOW SUMMARY")
        report.append("-" * 40)
        
        for workflow_name, stats in workflow_stats.items():
            token_stats = stats["token_stats"]["total_tokens"]
            report.append(f"\n{workflow_name}:")
            report.append(f"  Successful runs: {stats['successful_runs']}")
            report.append(f"  Average tokens: {token_stats['mean']:.1f}")
            report.append(f"  Token range: {token_stats['min']} - {token_stats['max']}")
            report.append(f"  Standard deviation: {token_stats['stdev']:.1f}")
        
        report.append("\n" + "="*80)
        report.append("DETAILED BREAKDOWN BY WORKFLOW")
        report.append("="*80)
        
        for workflow_name, stats in workflow_stats.items():
            report.append(f"\n{workflow_name.upper()}")
            report.append("-" * len(workflow_name))
            
            # Overall stats
            total_stats = stats["token_stats"]["total_tokens"]
            input_stats = stats["token_stats"]["input_tokens"]
            output_stats = stats["token_stats"]["output_tokens"]
            
            report.append(f"\nOverall Token Usage:")
            report.append(f"  Total Tokens - Avg: {total_stats['mean']:.1f}, Range: {total_stats['min']}-{total_stats['max']}")
            report.append(f"  Input Tokens - Avg: {input_stats['mean']:.1f}, Range: {input_stats['min']}-{input_stats['max']}")
            report.append(f"  Output Tokens - Avg: {output_stats['mean']:.1f}, Range: {output_stats['min']}-{output_stats['max']}")
            
            # Step breakdown
            report.append(f"\nStep Breakdown:")
            for step_name, step_data in stats["step_breakdown"].items():
                report.append(f"  {step_name} ({step_data['model']}):")
                report.append(f"    Avg Total: {step_data['avg_total_tokens']:.1f}")
                report.append(f"    Avg Input: {step_data['avg_input_tokens']:.1f}")
                report.append(f"    Avg Output: {step_data['avg_output_tokens']:.1f}")
        
        return "\n".join(report)

    def save_results(self, workflow_stats: Dict, filename: str = None):
        """Save results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"token_analysis_{timestamp}.json"
        
        # Add metadata
        results = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "user_id": self.user_id,
                "analysis_type": "workflow_token_usage"
            },
            "workflow_stats": workflow_stats
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to: {filename}")
        return filename


def main():
    """Main function to run the token analysis"""
    print("Starting Token Usage Analysis for System Workflows")
    
    # Get user ID from environment or prompt
    user_id = os.environ.get("CURRENT_USER_ID")
    if not user_id:
        print("Please set CURRENT_USER_ID environment variable or run this through the main application")
        return
    
    try:
        # Create tracker
        tracker = TokenTracker(user_id)
        
        # Run analysis (5 runs per workflow by default)
        workflow_stats = tracker.run_workflow_analysis(num_runs=5)
        
        # Generate and print report
        report = tracker.generate_report(workflow_stats)
        print("\n" + report)
        
        # Save results
        filename = tracker.save_results(workflow_stats)
        
        print(f"\n=== Analysis Complete ===")
        print(f"Results saved to: {filename}")
        print(f"Analyzed {len(workflow_stats)} workflows")
        
        return workflow_stats
        
    except Exception as e:
        print(f"Error running analysis: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
