"""Validate the actual Compose model without a daemon or real credentials."""
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

import pytest

from scripts.compose_verification import VerificationCompose

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def compose_environment(tmp_path):
    if not shutil.which('docker') or subprocess.run(['docker', 'compose', 'version'], capture_output=True).returncode:
        pytest.skip('Docker Compose CLI is required to validate deployment')
    empty = tmp_path / 'empty.env'
    empty.write_text('')
    env = {**os.environ,
           'TUNNEL_TOKEN': 'unused-compose-fixture',
           'OPENROUTER_API_KEY': '',
           'FEEDASTROLABE_OLLAMA_TOKEN_FILE': '',
           'FEEDASTROLABE_DELIVERY_CONFIG_FILE': '', 'COMPOSE_PROFILES': ''}
    for key in ('COMPOSE_FILE', 'COMPOSE_ENV_FILES', 'COMPOSE_PROJECT_NAME',
                'FEEDASTROLABE_ACCESS_MODE', 'CF_ACCESS_TEAM_DOMAIN', 'CF_ACCESS_AUD',
                'FEEDASTROLABE_PUBLIC_HOSTS'):
        env.pop(key, None)
    return ['docker', 'compose', '--env-file', str(empty)], env


def resolved(command, env):
    result = subprocess.run(command+['config', '--format', 'json'], cwd=ROOT, env=env,
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def test_default_file_discovery_and_tunnel_authentication(compose_environment):
    command, env = compose_environment
    assert sorted(path.name for path in ROOT.glob('compose*.y*ml')) == ['compose.yml']
    model = resolved(command, env)
    assert model['name'] == 'feedastrolabe'
    assert set(model['services']) == {'web', 'worker', 'observer', 'renderer', 'tunnel'}
    web = model['services']['web']
    assert web['environment']['FEEDASTROLABE_ACCESS_MODE'] == 'tunnel'
    for key in ('CF_ACCESS_TEAM_DOMAIN', 'CF_ACCESS_AUD', 'FEEDASTROLABE_PUBLIC_HOSTS'):
        assert web['environment'][key] == ''
    tunnel = model['services']['tunnel']
    assert tunnel['command'] == ['tunnel', '--no-autoupdate', 'run']
    assert tunnel['environment'] == {'TUNNEL_TOKEN': env['TUNNEL_TOKEN']}
    assert not tunnel.get('secrets')
    assert 'volumes' not in tunnel
    assert not model.get('secrets')
    for name in ('web', 'worker', 'observer', 'renderer'):
        assert 'TUNNEL_TOKEN' not in model['services'][name].get('environment', {})
    assert model['services']['observer']['depends_on']['renderer']['condition'] == 'service_healthy'
    assert tunnel['depends_on']['web']['condition'] == 'service_healthy'


def test_compose_selects_shared_dockerfile_roles(compose_environment):
    model = resolved(*compose_environment)
    for name in ('web', 'worker', 'observer', 'renderer'):
        build = model['services'][name]['build']
        assert build['context'] == str(ROOT)
        assert build.get('dockerfile', 'Dockerfile') == 'Dockerfile'
        assert build['target'] == ('renderer' if name == 'renderer' else 'app')


def test_dotenv_supplies_tunnel_token_without_credential_file(compose_environment):
    command, env = compose_environment
    keys = ('TUNNEL_TOKEN',)
    dotenv = Path(command[-1])
    dotenv.write_text('\n'.join(key+'='+env[key] for key in keys)+'\n')
    for key in keys:
        env.pop(key)
    model = resolved(command, env)
    assert model['services']['web']['environment']['FEEDASTROLABE_ACCESS_MODE'] == 'tunnel'
    tunnel = model['services']['tunnel']
    assert tunnel['environment']['TUNNEL_TOKEN'] == 'unused-compose-fixture'
    assert not tunnel.get('secrets') and not tunnel.get('volumes')
    assert 'unused-compose-fixture' not in json.dumps(tunnel['command'])
    for name in ('web', 'worker', 'observer', 'renderer'):
        assert 'unused-compose-fixture' not in json.dumps(model['services'][name])
    subprocess.run(command+['config', '--quiet'], cwd=ROOT, env=env, check=True, capture_output=True)


def test_default_network_volume_and_container_isolation(compose_environment):
    model = resolved(*compose_environment)
    assert model['volumes']['reader-data']['name'] == 'feedastrolabe_reader-data'
    assert model['volumes']['renderer-ipc']['name'] == 'feedastrolabe_renderer-ipc'
    assert model['networks']['reader']['driver'] == 'bridge'
    for name, service in model['services'].items():
        assert not service.get('ports')
        assert service['read_only'] is True
        assert service['cap_drop'] == ['ALL']
        assert 'no-new-privileges:true' in service['security_opt']
        assert not service.get('privileged')
        if name != 'renderer':
            assert set(service['networks']) == {'reader'}
    renderer = model['services']['renderer']
    assert renderer['network_mode'] == 'none'
    assert [(volume['source'], volume['target']) for volume in renderer['volumes']] == [('renderer-ipc', '/run/observer')]
    assert not renderer.get('secrets') and not renderer.get('environment')
    assert int(renderer['mem_limit']) == 512*1024*1024 and int(renderer['pids_limit']) == 128
    assert float(renderer['cpus']) == 1
    for name in ('web', 'worker', 'observer'):
        assert any(volume['source'] == 'reader-data' and volume['target'] == '/data'
                   for volume in model['services'][name]['volumes'])


@pytest.mark.parametrize('empty', [False, True])
def test_missing_tunnel_token_fails_closed(compose_environment, empty):
    command, env = compose_environment
    env.pop('TUNNEL_TOKEN')
    if empty:
        env['TUNNEL_TOKEN'] = ''
    result = subprocess.run(command+['config', '--quiet'], cwd=ROOT, env=env, text=True, capture_output=True)
    assert result.returncode != 0 and 'TUNNEL_TOKEN' in result.stderr


def test_explicit_app_jwt_configuration_is_preserved(compose_environment):
    command, env = compose_environment
    settings = {'FEEDASTROLABE_ACCESS_MODE': 'cloudflare',
                'CF_ACCESS_TEAM_DOMAIN': 'https://fixture.cloudflareaccess.com',
                'CF_ACCESS_AUD': 'fixture-audience', 'FEEDASTROLABE_PUBLIC_HOSTS': 'reader.example.com'}
    model = resolved(command, {**env, **settings})
    for key, value in settings.items():
        assert model['services']['web']['environment'][key] == value


def test_optional_integrations_need_no_extra_mounts(compose_environment):
    model = resolved(*compose_environment)
    assert not model.get('secrets')
    for name in ('web', 'worker'):
        assert not model['services'][name].get('secrets')
        for key in ('FEEDASTROLABE_OLLAMA_TOKEN_FILE', 'FEEDASTROLABE_DELIVERY_CONFIG_FILE'):
            assert model['services'][name]['environment'][key] == ''
    command, env = compose_environment
    paths = {'FEEDASTROLABE_OLLAMA_TOKEN_FILE': '/data/ollama-token',
             'FEEDASTROLABE_DELIVERY_CONFIG_FILE': '/data/delivery-config.json'}
    configured = resolved(command, {**env, **paths})
    for name in ('web', 'worker'):
        for key, value in paths.items():
            assert configured['services'][name]['environment'][key] == value


def test_verification_ignores_operator_settings_and_cleans_up(compose_environment, monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','operator-synthetic-key')
    for key in ('FEEDASTROLABE_OLLAMA_TOKEN_FILE', 'FEEDASTROLABE_DELIVERY_CONFIG_FILE'):
        monkeypatch.setenv(key, '/operator/private-path')
    monkeypatch.setenv('CF_ACCESS_TEAM_DOMAIN', 'https://operator.cloudflareaccess.com')
    monkeypatch.setenv('FEEDASTROLABE_ACCESS_MODE', 'cloudflare')
    monkeypatch.setenv('TUNNEL_TOKEN', 'operator-synthetic-token')
    monkeypatch.setenv('COMPOSE_PROFILES', '*')
    monkeypatch.setenv('COMPOSE_FILE', '/operator/compose-file')
    with VerificationCompose('feedastrolabe-contract-verify') as target:
        model = resolved(target.command, target.env)
        assert set(model['services']) == {'web', 'worker', 'observer', 'renderer'}
        assert model['services']['web']['environment']['FEEDASTROLABE_ACCESS_MODE'] == 'local'
        assert model['services']['web']['environment']['CF_ACCESS_TEAM_DOMAIN'] == ''
        assert model['volumes']['reader-data']['name'] == 'feedastrolabe-contract-verify_reader-data'
        for service in model['services'].values():
            assert not service.get('ports')
        for name in ('web', 'worker'):
            assert model['services'][name]['image'] == 'feedastrolabe-contract-verify:local'
            for key in ('FEEDASTROLABE_OLLAMA_TOKEN_FILE', 'FEEDASTROLABE_DELIVERY_CONFIG_FILE'):
                assert model['services'][name]['environment'][key] == ''
        folder = Path(target.directory.name)
        assert not model.get('secrets')
        assert target.env['TUNNEL_TOKEN'] == 'unused-verification-fixture'
        assert target.env['OPENROUTER_API_KEY'] == ''
        assert 'operator-synthetic-key' not in json.dumps(model)
        assert 'operator-synthetic-token' not in json.dumps(model)
        assert not list(folder.glob('*token*'))
    assert not folder.exists()


def test_openrouter_environment_is_optional_and_confined(compose_environment):
    command,env=compose_environment
    model=resolved(command,{**env,'OPENROUTER_API_KEY':'fixture-openrouter-key'})
    for name in ('web','worker'):
        assert model['services'][name]['environment']['OPENROUTER_API_KEY']=='fixture-openrouter-key'
    for name in ('observer','renderer','tunnel'):
        assert 'OPENROUTER_API_KEY' not in model['services'][name].get('environment',{})


@pytest.mark.parametrize('script', ['verify_container.py', 'verify_observer.py'])
def test_acceptance_refuses_production_project(script):
    result = subprocess.run([sys.executable, str(ROOT/'scripts'/script), '--project', 'feedastrolabe'],
                            text=True, capture_output=True)
    assert result.returncode == 2 and '-verify' in result.stderr


def test_embedded_acceptance_programs_compile():
    for name in ('verify_container.py', 'verify_observer.py'):
        tree = ast.parse((ROOT/'scripts'/name).read_text())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ('python', 'code') and node.args and isinstance(node.args[0], ast.Constant)):
                compile(textwrap.dedent(node.args[0].value), name+' embedded program', 'exec')
