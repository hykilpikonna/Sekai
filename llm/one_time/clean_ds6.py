"""
This script is used to clean the text story data from Project Sekai and prepare it for LoRA fine-tuning.
"""
import json
from pathlib import Path

BASE_DIR = Path(r"C:\ws\Sekai\S3\sekai-jp-assets")

if __name__ == '__main__':
    # Read from json
    src = Path(__file__).parent
    parsed = json.loads((src / '../data/parsed_chats.json').read_text('utf-8'))

    # DS6: Convert to conversational training format v2
    # [{
    #     "system": "ユーザーの入力を続けて、プロセカメンバー間の会話ダイアログを作成してください。繰り返しを避けてください。"
    #     "instruction "### 瑞希：まふゆ、こんにちは！\n### まふゆ：こんにちは！",
    #     "output": "### 瑞希：いいね！",
    #     "history": []
    # }, ...]
    training_data = []
    training_data_openai = []
    last_chat = None
    for conversation in parsed:
        # File too large ;-;
        # Limit to only conversations where 瑞希 spoke
        if '瑞希' not in str(conversation):
            continue

        history = ""
        for i, talk in enumerate(conversation):
            speaker = talk.get('speaker') or talk.get('title')
            line = f"### {speaker}: {talk['text']};;"

            if i != 0:
                training_data.append({
                    "system": "ユーザーの入力を続けて、プロセカメンバー間の会話ダイアログを作成してください。繰り返しを避けてください。",
                    "instruction": history,
                    "output": line
                })

                # Also save in openai's format. Format example:
                # {"messages": [
                #   {"role": "system", "content": "Marv is a factual chatbot that is also sarcastic."},
                #   {"role": "user", "content": "What's the capital of France?"},
                #   {"role": "assistant", "content": "Paris, as if everyone doesn't know that already."}
                # ]}
                training_data_openai.append({"messages": [
                    {"role": "system", "content": "ユーザーの入力を続けて、プロセカメンバー間の会話ダイアログを作成してください。繰り返しを避けてください。"},
                    {"role": "user", "content": history},
                    {"role": "assistant", "content": line}
                ]})
            if history != "":
                history += '\n'
            history += line

        last_chat = conversation

    Path(src / '../data/train/ds6.mzk.json').write_text(json.dumps(training_data, ensure_ascii=False, indent=2), 'utf-8')
    Path(src / '../data/train/ds6-openai.mzk.jsonl').write_text('\n'.join(json.dumps(x, ensure_ascii=False) for x in training_data_openai), 'utf-8')
