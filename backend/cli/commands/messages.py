import sys
import json
from backend.learner.chat_parser import ChatParser
from backend.cli.utils import resolve_file_path


def cmd_messages(args):
    try:
        file_path = resolve_file_path(args.file_path)
        
        if not file_path.exists():
            print(f"Error: File not found: {file_path}")
            sys.exit(1)
        
        parser = ChatParser(model='gpt-5', debug=False)
        
        if file_path.suffix == '.json':
            with open(file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            cleaned_json = parser._clean_json_messages(json_data)
            messages = parser._extract_user_messages_from_json(cleaned_json)
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                md_text = f.read()
            messages = parser._extract_user_messages(md_text)
        
        if not messages:
            print(f"No user messages found in {file_path.name}")
            return
        
        # Display results
        print("=" * 80)
        print(f"USER MESSAGES from: {file_path.name}")
        print("=" * 80)
        print()
        
        for i, msg in enumerate(messages, 1):
            print(f"{i}. [Line {msg['line_num']}]")
            # Wrap long messages
            text = msg['text']
            if len(text) > 100:
                # Show first 100 chars, then continue on next lines
                print(f"   {text[:100]}")
                remaining = text[100:]
                while remaining:
                    print(f"   {remaining[:100]}")
                    remaining = remaining[100:]
            else:
                print(f"   {text}")
            print()
        
        print(f"Total: {len(messages)} message(s)")
        print()
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
