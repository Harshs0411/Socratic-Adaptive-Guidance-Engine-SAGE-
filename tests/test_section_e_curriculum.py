"""
Test Suite for Section E: Rich Curriculum & Loader.
Verifies binary_search_curriculum.json structure, Pydantic schema validation,
and seamless fallback / conversion to legacy Curriculum models.
"""

import unittest
from multi_agent_tutor.app.schemas.curriculum import (
    RichCurriculum,
    Curriculum,
    CurriculumConcept,
)
from multi_agent_tutor.app.curriculum_loader import (
    load_rich_curriculum,
    load_curriculum_concepts,
)


class TestSectionECurriculum(unittest.TestCase):

    def test_01_gold_curriculum_loads_and_validates(self):
        """Verify binary_search_curriculum.json conforms to RichCurriculum schema."""
        rich = load_rich_curriculum("Binary Search")
        self.assertIsNotNone(rich, "Failed to load binary search gold curriculum.")
        self.assertIsInstance(rich, RichCurriculum)
        self.assertGreaterEqual(len(rich.topics), 4, "Must contain at least 4 topics.")

        print("\n" + "=" * 80)
        print("SECTION E: GOLD BINARY SEARCH CURRICULUM AUDIT".center(80))
        print("=" * 80)

        for t_idx, topic in enumerate(rich.topics, 1):
            print(f"\n[Topic {t_idx}] {topic.title} (ID: {topic.topic_id}, Difficulty: {topic.difficulty})")
            self.assertTrue(len(topic.subtopics) >= 1, f"Topic {topic.topic_id} must have subtopics.")

            for s_idx, sub in enumerate(topic.subtopics, 1):
                print(f"  └─ Subtopic {s_idx}: {sub.name} (ID: {sub.subtopic_id})")
                print(f"     Objectives: {len(sub.learning_objectives)} | Worked Examples: {len(sub.worked_examples)} | Analogies: {len(sub.analogies)} | Questions: {len(sub.question_bank)}")
                
                # Check requirement: 2+ worked examples
                self.assertGreaterEqual(len(sub.worked_examples), 2, f"Subtopic {sub.subtopic_id} must have >= 2 worked examples.")
                for ex in sub.worked_examples:
                    self.assertTrue(bool(ex.title and ex.problem and ex.step_by_step_solution and ex.key_takeaway))

                # Check requirement: 3-tier question bank with model answers
                tiers = {q.difficulty_tier for q in sub.question_bank}
                self.assertTrue({1, 2, 3}.issubset(tiers), f"Subtopic {sub.subtopic_id} must have Tier 1, 2, and 3 questions.")
                for q in sub.question_bank:
                    self.assertTrue(bool(q.question and q.expected_answer and q.evaluation_criteria))

        print("\n" + "=" * 80)

    def test_02_conversion_to_legacy_curriculum(self):
        """Verify RichCurriculum converts cleanly to legacy Curriculum and CurriculumConcept DAG."""
        rich = load_rich_curriculum("Binary Search")
        legacy_curr = rich.to_curriculum()
        self.assertIsInstance(legacy_curr, Curriculum)
        self.assertGreaterEqual(len(legacy_curr.concepts), 4)

        for concept in legacy_curr.concepts:
            self.assertIsInstance(concept, CurriculumConcept)
            self.assertTrue(bool(concept.concept_id and concept.name and concept.description))

        concepts_direct = load_curriculum_concepts("binary_search")
        self.assertIsNotNone(concepts_direct)
        self.assertGreaterEqual(len(concepts_direct), 4)
        print("✅ RichCurriculum to legacy Curriculum DAG conversion verified.")


if __name__ == "__main__":
    unittest.main()
