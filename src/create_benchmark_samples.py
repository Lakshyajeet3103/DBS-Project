"""Materialize inspectable fictional documents. Run only when updating sample fixtures."""
import json
from pathlib import Path
from src.benchmark_data import TOPICS, CONTEXTS, TRIGGERS, ACTIONS


def main():
    root = Path(__file__).resolve().parents[1]/'data/benchmark_samples'
    folder = root/'documents'
    folder.mkdir(parents=True, exist_ok=True)
    queries = []
    for topic, procedure in TOPICS:
        paragraphs = []
        for context in CONTEXTS:
            for trigger in TRIGGERS:
                queries.append({'text': f'How should {context} handle {topic} after {trigger}?'})
                for closing in ACTIONS:
                    paragraphs.append(f'Guidance on {topic} for {context}. Following {trigger}, {procedure}. {closing}')
        (folder/(topic.replace(' ', '-')+'.md')).write_text(
            f'# Fictional practice scenarios: {topic}\n\n'+'\n\n'.join(paragraphs)+'\n', encoding='utf-8')
    (root/'queries.jsonl').write_text('\n'.join(json.dumps(q) for q in queries)+'\n', encoding='utf-8')
    print(f'Wrote {len(TOPICS)} sample documents with 10000 fictional paragraphs and {len(queries)} query prompts.')


if __name__ == '__main__':
    main()
