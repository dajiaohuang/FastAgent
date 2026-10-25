import asyncio
import unittest

from fastagent.agents.coordinator import AgentCoordinator
from fastagent.kanban import Kanban


class CoordinatorForwardLogicalReferenceTests(unittest.TestCase):
    def test_add_batch_resolves_references_to_later_cards(self):
        coordinator = AgentCoordinator.__new__(AgentCoordinator)
        coordinator._kanban = Kanban()
        updates = [
            {
                "action": "add",
                "temp_id": "dependent",
                "card_type": "execution",
                "metadata": {
                    "depends_on": ["producer"],
                    "planning_card_id": "plan",
                    "target_response_logical_id": "response",
                },
            },
            {"action": "add", "temp_id": "plan", "card_type": "planning"},
            {"action": "add", "temp_id": "producer", "card_type": "execution"},
            {"action": "add", "temp_id": "response", "card_type": "response"},
        ]

        result = asyncio.run(
            coordinator.execute_kanban_updates(updates, agent_name="HostAgent", step=1)
        )
        card_ids = result["logical_id_mapping"]
        dependent = coordinator._kanban.get_card(card_ids["dependent"])

        self.assertEqual(dependent.metadata["depends_on"], [card_ids["producer"]])
        self.assertEqual(dependent.metadata["planning_card_id"], card_ids["plan"])
        self.assertEqual(dependent.metadata["target_response_card_id"], card_ids["response"])
        self.assertNotIn("target_response_logical_id", dependent.metadata)
        self.assertEqual(result["errors"], [])


if __name__ == "__main__":
    unittest.main()
