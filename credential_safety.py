"""Keep provider credentials out of child processes and user-visible errors."""


def credential_name(name):
    return any(word in name.upper() for word in
               ('API_KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'CREDENTIAL', 'AUTHORIZATION'))


def without_credentials(environment):
    return {name: value for name, value in environment.items() if not credential_name(name)}
