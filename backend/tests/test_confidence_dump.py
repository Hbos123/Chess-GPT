

def make_node(**kwargs):
    node = {
        "id": "pv-0",
        "parent_id": None,
        "ConfidencePercent": 50,
        "ply_from_S0": 0,
        "move_from_parent": None,
        "has_branches": False,
        "frozen_confidence": None,
        "initial_confidence": None,
        "insufficient_confidence": False,
        "fen": "8/8/8/8/8/8/8/8 w - - 0 1",
        "extended_moves": None,
    }
    node.update(kwargs)
    return node


def main():
    nodes = [
        make_node(
            id="pv-0",
            ConfidencePercent=85,
            ply_from_S0=0,
            move_from_parent=None,
            has_branches=False,
        ),
        make_node(
            id="pv-1",
            parent_id="pv-0",
            ConfidencePercent=75,
            ply_from_S0=1,
            move_from_parent="e2e4",
        ),
        make_node(
            id="pv-2",
            parent_id="pv-1",
            ConfidencePercent=65,
            ply_from_S0=2,
            move_from_parent="e7e5",
            has_branches=True,
            frozen_confidence=60,
            initial_confidence=55,
            insufficient_confidence=True,
            extended_moves={"e7e5": -30},
        ),
        make_node(
            id="iter-alt-0",
            parent_id="pv-2",
            ConfidencePercent=None,
            ply_from_S0=None,
            move_from_parent=None,
            has_branches=False,
            frozen_confidence=None,
            initial_confidence=None,
            insufficient_confidence=None,
            extended_moves=None,
        ),
    ]
    from backend.confidence_engine import _print_full_node_dump
    _print_full_node_dump(nodes, "TEST DUMP")


if __name__ == "__main__":
    main()

