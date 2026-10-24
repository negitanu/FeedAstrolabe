"""Temporary local-only settings for isolated Compose acceptance projects."""
import json
import os
from pathlib import Path
import re
import tempfile


class VerificationCompose:
    services = ('web', 'worker', 'renderer', 'observer')

    def __init__(self, project):
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*-verify', project):
            raise ValueError('Use an isolated project name ending in -verify')
        self.root = Path(__file__).resolve().parent.parent
        self.directory = tempfile.TemporaryDirectory(prefix='feedastrolabe-verify-')
        folder = Path(self.directory.name)
        env_file = folder / 'empty.env'
        env_file.write_text('')
        override = folder / 'verification.json'
        override.write_text(json.dumps({'services': {
            'web': {'image': project+':local', 'environment': {'FEEDASTROLABE_ACCESS_MODE': 'local'}},
            'worker': {'image': project+':local'},
            'observer': {'image': project+':local'},
            'renderer': {'image': project+'-renderer:local'},
            'tunnel': {'profiles': ['external-verification-disabled']},
        }}))
        self.command = ['docker', 'compose', '--env-file', str(env_file), '-p', project,
                        '-f', str(self.root / 'compose.yml'), '-f', str(override)]
        self.env = {**os.environ,
                    'COMPOSE_PROFILES': '',
                    'FEEDASTROLABE_ACCESS_MODE': 'local',
                    'CF_ACCESS_TEAM_DOMAIN': '',
                    'CF_ACCESS_AUD': '',
                    'FEEDASTROLABE_PUBLIC_HOSTS': '',
                    'TUNNEL_TOKEN': 'unused-verification-fixture',
                    'OPENROUTER_API_KEY': '',
                    'FEEDASTROLABE_OLLAMA_TOKEN_FILE': '',
                    'FEEDASTROLABE_DELIVERY_CONFIG_FILE': '',
                    'FEEDASTROLABE_OLLAMA_LOCAL_HOST': '127.0.0.1'}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.directory.cleanup()
