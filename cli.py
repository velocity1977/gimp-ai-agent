import sys
import os
import argparse

from orchestrator import GimpAgentOrchestrator, SYSTEM_PROMPT
from llm_providers import OllamaProvider, OpenAIProvider, GeminiProvider

# Ensure UTF-8 console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def print_banner(provider_name, routing_mode):
    print("=" * 65)
    print(" 🎨 GIMP AGENTIC AI — NATURAL LANGUAGE IMAGE EDITOR")
    print(f" GIMP Target: 3.2.4 | Engine: {provider_name}")
    print(f" Tool Mode:   {'Category Routing (Core + Dynamic)' if routing_mode else 'All Tools (50 Tools Loaded)'}")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(
        description="GIMP Agentic AI — Interactive Image Editing CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py                         # Default: Ollama (qwen2.5:3b) with Category Routing
  python cli.py ollama qwen2.5:7b       # Ollama with specific model
  python cli.py gemini                  # Google Gemini (gemini-2.5-flash)
  python cli.py openai gpt-4o           # OpenAI GPT-4o
  python cli.py gemini --all-tools      # Gemini with all 50 tools loaded upfront
        """
    )
    parser.add_argument("provider", nargs="?", default="ollama", choices=["ollama", "openai", "gemini"], help="LLM Provider")
    parser.add_argument("model", nargs="?", default=None, help="Custom model name")
    parser.add_argument("--all-tools", action="store_true", help="Load all 50 tools upfront (disables Category Routing)")

    args = parser.parse_args()
    use_routing = not args.all_tools

    # Instantiate Provider
    if args.provider == "openai":
        model = args.model or "gpt-4o"
        provider = OpenAIProvider(model=model)
    elif args.provider == "gemini":
        model = args.model or "gemini-2.5-flash"
        provider = GeminiProvider(model=model)
    else:
        model = args.model or "qwen2.5:3b"
        provider = OllamaProvider(model=model)

    orchestrator = GimpAgentOrchestrator(llm_provider=provider, use_category_routing=use_routing)

    print_banner(provider.get_name(), use_routing)

    print(f"\n[Environment Check]")
    status = orchestrator.check_environment()
    
    gimp_status_str = "[OK] Connected" if status["gimp"] else f"[NOT CONNECTED] ({status['details']['gimp']})"
    llm_status_str = "[OK] Connected" if status["llm"] else f"[NOT CONNECTED] ({status['details']['llm']})"

    print(f"  * GIMP Socket Server (port 9877): {gimp_status_str}")
    print(f"  * LLM Provider ({provider.get_name()}): {llm_status_str}")
    print(f"  * Active Tools in Context:        {len(orchestrator.tools)} tools")

    if not status["gimp"]:
        print("\n[NOTE] GIMP is not connected yet.")
        print("  1. Open GIMP 3.2.4")
        print("  2. Go to: Tools > AI Agent > Start AI Agent Server")
        print("  (You can still type requests once GIMP is started!)\n")

    print("\nCommands:")
    print("  * Type your editing request in plain English")
    print("  * 'reset' / 'clear' to start a fresh conversation")
    print("  * 'exit' / 'quit' to end session")
    print("-" * 65)

    while True:
        try:
            user_input = input("\ngimp-ai > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Exiting GIMP AI Agent. Goodbye!")
                break
            if user_input.lower() in ("reset", "clear"):
                orchestrator.reset_session()
                print(f"[Context cleared. Fresh session started with {len(orchestrator.tools)} tools active.]\n")
                continue

            print("\nProcessing request...")
            def on_progress(step_text):
                print(f"  --> {step_text}")

            response = orchestrator.process_user_turn(user_input, stream_callback=on_progress)
            print(f"\n[AI Response]\n{response}\n")

        except (KeyboardInterrupt, EOFError):
            print("\nSession ended.")
            break
        except Exception as e:
            print(f"\n[Error] {e}")


if __name__ == "__main__":
    main()
