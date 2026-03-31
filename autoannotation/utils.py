import numbers

def seconds_to_str(total_seconds):
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    total_hours = total_minutes // 60
    hours = total_hours % 24
    total_days = total_hours // 24
    if total_days > 0:
        return f'{total_days:.0f}d, {hours:.0f}h, {minutes:.0f}m, {seconds:.1f}s'
    elif total_hours > 0:
        return f'{hours:.0f}h, {minutes:.0f}m, {seconds:.1f}s'
    elif total_minutes > 0:
        return f'{minutes:.0f}m, {seconds:.1f}s'
    else:
        return f'{seconds:.1f}s'

def s_if_plural(num_or_collection):
    if isinstance(num_or_collection, numbers.Number):
        return "s" if num_or_collection != 1 else ""
    return "s" if len(num_or_collection) != 1 else ""
