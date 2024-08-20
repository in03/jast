from pathlib import Path

import yaml


def install_hooks():
    hook_config = {
        'repo': 'local',
        'hooks': [
            {
                'id': 'jast-pre-push',
                'name': 'jast pre-push hook',
                'entry': 'jast-push-hook.sh',
                'language': 'script',
                'stages': ['push']
            },
            {
                'id': 'jast-pre-pull',
                'name': 'jast pre-pull hook',
                'entry': 'jast-pull-hook.sh',
                'language': 'script',
                'stages': ['pull']
            }
        ]
    }
    config_path = Path('.pre-commit-config.yaml')
    if config_path.exists():
        with config_path.open('r') as f:
            config = yaml.safe_load(f)
        config['repos'].append(hook_config)
    else:
        config = {'repos': [hook_config]}
    
    with config_path.open('w') as f:
        yaml.safe_dump(config, f)

# Call this function within your CLI
install_hooks()
