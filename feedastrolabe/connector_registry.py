"""Extensible registered policies; arbitrary adapters/endpoints are never accepted."""
from . import security_adapters as security,network_adapters as network
PROVIDERS={**security.PROVIDERS,**network.PROVIDERS}

def contract(provider,value):
    if provider in security.PROVIDERS:security.endpoint(provider,value)
    elif provider in network.PROVIDERS:network.contract(provider,value)
    else:raise ValueError('provider-policy')

def endpoint(provider,value):
    contract(provider,value)
    return (security if provider in security.PROVIDERS else network).endpoint(provider,value)

def validate(provider,value,payload):
    contract(provider,value)
    return (security if provider in security.PROVIDERS else network).validate(provider,value,payload)
