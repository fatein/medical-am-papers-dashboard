"""Preserve deliberate filters while keeping an all-records view up to date."""


def sync_options(state, key, options):
    previous = state.get('_options_' + key)
    selected = state.get(key)
    if selected is not None and previous is not None and previous != options:
        state[key] = list(options) if set(selected) == set(previous) else [
            value for value in selected if value in options]
    state['_options_' + key] = list(options)


def sync_year_range(state, bounds):
    previous = state.get('_year_bounds')
    selected = state.get('years')
    if selected is not None and previous is not None and previous != bounds:
        state['years'] = bounds if tuple(selected) == tuple(previous) else tuple(
            max(bounds[0], min(bounds[1], value)) for value in selected)
    state['_year_bounds'] = bounds
