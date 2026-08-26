import json
plan_data = {
    'tasks': [
        {'depends_on': []},
        {'depends_on': [0]},
        {'depends_on': [1]},
        {'depends_on': [2]},
        {'depends_on': [3]},
        {'depends_on': [4]}
    ]
}
for i, item in enumerate(plan_data['tasks']):
    dep = item.get("depends_on", [])
    print(f'Task {i}: depends_on = {dep}, types = {[type(v) for v in dep]}')