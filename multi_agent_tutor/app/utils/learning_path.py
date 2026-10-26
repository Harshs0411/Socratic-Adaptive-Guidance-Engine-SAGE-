def update_learning_path(
    learning_path,
    mastery_map
):
    for step in learning_path.steps:

        step.mastery = mastery_map.get(
            step.concept_id,
            step.mastery
        )
        step.mastery >=0.85
        step.status = "mastered" if step.mastery >= 0.85 else "not_mastered"