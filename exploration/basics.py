from langgraph.graph import StateGraph, END
from typing import TypedDict

# ── State definition ──────────────────────────────────────────
# TypedDict defines what data flows through the graph
class SimpleState(TypedDict):
    value: int
    message: str

# ── Nodes are just Python functions ───────────────────────────
def double_it(state: SimpleState) -> SimpleState:
    print(f'Node double_it: value is {state["value"]}')
    return {'value': state['value'] * 2, 'message': 'doubled'}

def add_ten(state: SimpleState) -> SimpleState:
    print(f'Node add_ten: value is {state["value"]}')
    return {'value': state['value'] + 10, 'message': 'added ten'}

# ── Build the graph ───────────────────────────────────────────
graph = StateGraph(SimpleState)
graph.add_node('double', double_it)
graph.add_node('add', add_ten)
graph.add_edge('double', 'add')        # double -> add
graph.add_edge('add', END)              # add -> done
graph.set_entry_point('double')

app = graph.compile()

# ── Run it ────────────────────────────────────────────────────
result = app.invoke({'value': 5, 'message': 'start'})
print(f'Final value: {result["value"]}')  # should be 20 (5*2+10)