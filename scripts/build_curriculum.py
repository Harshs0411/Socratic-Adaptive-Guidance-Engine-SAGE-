import json
import os
from multi_agent_tutor.app.schemas.curriculum import RichCurriculum

curriculum_data = {
  "curriculum_id": "binary_search_gold_v2",
  "title": "Binary Search & Algorithmic Problem Solving",
  "domain": "Algorithms & Data Structures",
  "description": "Comprehensive 6-topic structured curriculum covering fundamentals, search space reduction, loop implementation, off-by-one edge cases, boundary variants, and answer-space optimization.",
  "topics": [
    {
      "topic_id": "binary_search_fundamentals",
      "title": "Binary Search Fundamentals",
      "description": "Core mechanics of sorted search spaces, robust midpoint calculation, and basic elimination.",
      "prerequisites": [],
      "difficulty": 1,
      "subtopics": [
        {
          "subtopic_id": "bs_array_invariants",
          "name": "Sorted Array Preconditions & Search Space",
          "description": "Understanding why monotonicity and sorted order are mandatory for binary elimination.",
          "explanation_outline": [
            "Binary search requires a sorted or monotonic domain.",
            "Comparing against the midpoint divides the array into two halves.",
            "One entire half is definitively discarded based on the comparison."
          ],
          "learning_objectives": [
            "Explain why binary search strictly requires a sorted or monotonic collection.",
            "Identify the search space boundaries [low, high] at initialization."
          ],
          "worked_examples": [
            {
              "title": "Target Present in Odd-Length Array",
              "problem": "Search for target 7 in sorted array [1, 3, 5, 7, 9, 11, 13].",
              "step_by_step_solution": [
                "1. Initialize low = 0, high = 6. Mid = 0 + (6 - 0) // 2 = 3.",
                "2. Array value at index 3 is 7.",
                "3. Array[3] == target (7). Target found immediately in 1 comparison!"
              ],
              "key_takeaway": "When the target equals the middle element, the search terminates successfully with the matching index.",
              "visuals": [
                {
                  "visual_id": "vis_ex1_trace",
                  "title": "Direct Hit Comparison",
                  "type": "trace_table",
                  "content": "| Step | Low | High | Mid | Arr[Mid] | Comparison | Action |\n|---|---|---|---|---|---|---|\n| 1 | 0 | 6 | 3 | 7 | 7 == 7 | Match found! Return index 3 |",
                  "caption": "Step 1: The midpoint calculation points directly to target 7."
                }
              ]
            },
            {
              "title": "Target Absent in Even-Length Array",
              "problem": "Search for target 6 in sorted array [2, 4, 8, 10].",
              "step_by_step_solution": [
                "1. low = 0, high = 3. mid = 0 + (3 - 0) // 2 = 1. arr[1] = 4.",
                "2. 6 > 4, so target must lie in the right half. Update low = mid + 1 = 2.",
                "3. low = 2, high = 3. mid = 2 + (3 - 2) // 2 = 2. arr[2] = 8.",
                "4. 6 < 8, so target must lie in left half. Update high = mid - 1 = 1.",
                "5. Now low = 2 > high = 1. Pointers have crossed! Target 6 is absent."
              ],
              "key_takeaway": "When low exceeds high, the search space is exhausted and the target is guaranteed not present.",
              "visuals": [
                {
                  "visual_id": "vis_ex2_table",
                  "title": "Exhausted Search Space Trace",
                  "type": "trace_table",
                  "content": "| Step | Low | High | Mid | Arr[Mid] | Comparison | Action |\n|---|---|---|---|---|---|---|\n| 1 | 0 | 3 | 1 | 4 | 6 > 4 | Discard left half; Low = Mid + 1 (2) |\n| 2 | 2 | 3 | 2 | 8 | 6 < 8 | Discard right half; High = Mid - 1 (1) |\n| 3 | 2 | 1 | - | - | Low > High | Search space empty, return -1 |",
                  "caption": "Trace showing pointer crossover when target 6 is not in the array."
                }
              ]
            }
          ],
          "analogies": [
            "Looking up a word in a printed physical dictionary: you flip directly to the middle because alphabetical order guarantees which half contains the word.",
            "A high-low number guessing game: each guess tells you if the secret number is strictly higher or lower, cutting possibilities in half."
          ],
          "common_misconceptions": [
            "Believing binary search works on unsorted arrays by simply comparing against the middle element.",
            "Assuming binary search always requires extra memory like an auxiliary array."
          ],
          "visuals": [
            {
              "visual_id": "vis_flowchart_standard",
              "title": "Binary Search Algorithm Flowchart",
              "type": "mermaid",
              "content": "flowchart TD\n    A([Start: Low=0, High=n-1]) --> B{Low <= High?}\n    B -- Yes --> C[Mid = Low + (High-Low)/2]\n    C --> D{Arr[Mid] == Target?}\n    D -- Yes --> E([Return Mid: Found])\n    D -- No --> F{Arr[Mid] < Target?}\n    F -- Yes --> G[Low = Mid + 1]\n    F -- No --> H[High = Mid - 1]\n    G --> B\n    H --> B\n    B -- No --> I([Return -1: Not Found])",
              "caption": "Standard Binary Search decision flow showing the 3-way branch at each step."
            },
            {
              "visual_id": "vis_ascii_elimination",
              "title": "Binary Elimination Search Space",
              "type": "ascii",
              "content": "Initial: [ 1,  3,  5,  7,  9, 11, 13 ]\n          ^           ^           ^\n         Low         Mid         High\n\nIf Target > Arr[Mid]: Discard left half [1, 3, 5, 7]\nNext:                 [ 9, 11, 13 ]\n                        ^   ^   ^\n                       Low Mid High",
              "caption": "ASCII representation of discarding half the elements."
            }
          ],
          "question_bank": [
            {
              "question_id": "bs_f_q1",
              "difficulty_tier": 1,
              "question_type": "conceptual",
              "question": "Why does Binary Search require the input array to be sorted?",
              "expected_answer": "Because sorted order allows us to compare the target with the middle element and definitively discard the entire half where the target cannot possibly exist.",
              "evaluation_criteria": [
                "Mentions discarding or eliminating half the elements",
                "Relies on sorted order or monotonicity to make a definitive decision"
              ]
            },
            {
              "question_id": "bs_f_q2",
              "difficulty_tier": 2,
              "question_type": "objective",
              "question": "In an array of length 7 with indices 0 to 6, what is the initial middle index calculated using integer division?",
              "expected_answer": "3",
              "evaluation_criteria": [
                "Identifies index 3 correctly as 0 + (6 - 0) // 2"
              ]
            },
            {
              "question_id": "bs_f_q3",
              "difficulty_tier": 3,
              "question_type": "application",
              "question": "Can Binary Search be used to find an element in a rotated sorted array like [4, 5, 6, 7, 0, 1, 2]? Briefly explain why or why not.",
              "expected_answer": "Yes, because in any rotated sorted array, at least one of the two halves (left or right of mid) is always normally sorted. We can determine which half is sorted and check if the target falls in that range.",
              "is_transfer": True,
              "evaluation_criteria": [
                "Identifies that at least one half remains sorted",
                "Applies binary search logic based on checking the sorted half"
              ]
            }
          ]
        }
      ]
    },
    {
      "topic_id": "search_space_reduction",
      "title": "Search Space Reduction & Complexity",
      "description": "Understanding the halving principle, logarithmic time complexity O(log n), and pointer update rules.",
      "prerequisites": ["binary_search_fundamentals"],
      "difficulty": 2,
      "subtopics": [
        {
          "subtopic_id": "bs_halving_principle",
          "name": "The Halving Principle & Logarithmic Time Complexity",
          "description": "Mathematical intuition behind repeated halving and why binary search scales to billions of items.",
          "explanation_outline": [
            "Each comparison cuts the search space size from N to N/2.",
            "After k comparisons, the remaining elements are N / (2^k).",
            "When N / (2^k) = 1, k = log2(N). This makes binary search O(log N)."
          ],
          "learning_objectives": [
            "Compute the maximum number of comparisons for an array of size N.",
            "Explain why O(log N) operations require only ~30 comparisons for 1 billion items."
          ],
          "worked_examples": [
            {
              "title": "Halving Sequence for Size 16",
              "problem": "Show how the size of an array of 16 elements shrinks in the worst case.",
              "step_by_step_solution": [
                "Start: 16 elements (k = 0).",
                "Check 1: 16 / 2 = 8 elements remaining.",
                "Check 2: 8 / 2 = 4 elements remaining.",
                "Check 3: 4 / 2 = 2 elements remaining.",
                "Check 4: 2 / 2 = 1 element remaining. Total steps = 4 = log2(16)."
              ],
              "key_takeaway": "An array of 16 items takes at most 4 comparisons to locate any target or prove it absent."
            },
            {
              "title": "Scaling to 1,000,000 Elements",
              "problem": "Estimate the maximum comparisons needed to search 1 million sorted items.",
              "step_by_step_solution": [
                "1. Notice that 2^10 = 1,024 (~1 thousand).",
                "2. 2^20 = (2^10) * (2^10) = 1,048,576 (~1 million).",
                "3. Therefore, log2(1,000,000) <= 20."
              ],
              "key_takeaway": "Searching through 1 million items takes at most 20 comparisons with binary search, compared to 1,000,000 with linear search."
            }
          ],
          "analogies": [
            "Cutting a long piece of string in half repeatedly: even a kilometer of string shrinks to a few centimeters in just 15 cuts."
          ],
          "common_misconceptions": [
            "Thinking binary search is O(N) because you still have to look at the array.",
            "Confusing log2(N) with N/2."
          ],
          "visuals": [
            {
              "visual_id": "vis_halving_tree",
              "title": "Halving of Search Space",
              "type": "mermaid",
              "content": "graph TD\n    A[\"N = 1,000,000 (Step 0)\"] --> B[\"N = 500,000 (Step 1)\"]\n    B --> C[\"N = 250,000 (Step 2)\"]\n    C --> D[\"... (Step 10: N = 976)\"]\n    D --> E[\"... (Step 20: N = 1)\"]",
              "caption": "Rapid geometric shrinkage of search space from 1 million to 1 in 20 steps."
            }
          ],
          "question_bank": [
            {
              "question_id": "bs_h_q1",
              "difficulty_tier": 1,
              "question_type": "conceptual",
              "question": "What is the worst-case time complexity of Binary Search on an array of length N?",
              "expected_answer": "O(log N)",
              "evaluation_criteria": [
                "States O(log N) or logarithmic time"
              ]
            },
            {
              "question_id": "bs_h_q2",
              "difficulty_tier": 2,
              "question_type": "objective",
              "question": "What is the maximum number of comparisons needed to search a sorted list of 1024 elements?",
              "expected_answer": "10 or 11 comparisons (since 2^10 = 1024)",
              "evaluation_criteria": [
                "Answers 10 or 11 based on log2(1024) = 10"
              ]
            },
            {
              "question_id": "bs_h_q3",
              "difficulty_tier": 3,
              "question_type": "application",
              "question": "If doubling the size of an array from N to 2N adds how many additional comparisons in binary search?",
              "expected_answer": "Exactly 1 additional comparison, because log2(2N) = log2(N) + 1.",
              "is_transfer": True,
              "evaluation_criteria": [
                "Answers 1 additional comparison",
                "Explains using logarithmic properties"
              ]
            }
          ]
        }
      ]
    },
    {
      "topic_id": "loop_invariants_and_implementation",
      "title": "Writing the Loop & Pointer Invariants",
      "description": "Constructing the core binary search loop, updating low and high correctly, and tracing execution.",
      "prerequisites": ["search_space_reduction"],
      "difficulty": 2,
      "subtopics": [
        {
          "subtopic_id": "bs_loop_construction",
          "name": "Loop Construction & Pointer Updates",
          "description": "Implementing while (low <= high), avoiding infinite loops, and precise mid calculation.",
          "explanation_outline": [
            "Initialize low = 0, high = len(arr) - 1.",
            "Loop condition: while low <= high ensures single-element ranges [i, i] are inspected.",
            "Pointer updates: low = mid + 1 and high = mid - 1 strictly shrink the search space.",
            "Never write low = mid or high = mid without careful boundary reasoning, to prevent infinite loops."
          ],
          "learning_objectives": [
            "Write the standard while (low <= high) loop without errors.",
            "Explain why mid must be excluded with +1 or -1 in standard search."
          ],
          "worked_examples": [
            {
              "title": "Standard Loop Execution Trace",
              "problem": "Trace binary search for target 9 in [3, 9, 14, 20].",
              "step_by_step_solution": [
                "1. low = 0, high = 3. mid = 0 + (3-0)//2 = 1. arr[1] = 9.",
                "2. arr[mid] == 9 -> returns index 1 immediately."
              ],
              "key_takeaway": "Direct match at index 1 terminates the loop cleanly."
            },
            {
              "title": "Pointer Shrinking Step-by-Step",
              "problem": "Trace search for target 20 in [3, 9, 14, 20].",
              "step_by_step_solution": [
                "1. low = 0, high = 3. mid = 1 (val 9). 20 > 9 -> low = mid + 1 = 2.",
                "2. low = 2, high = 3. mid = 2 + (3-2)//2 = 2 (val 14). 20 > 14 -> low = mid + 1 = 3.",
                "3. low = 3, high = 3. mid = 3 (val 20). Match found at index 3!"
              ],
              "key_takeaway": "When low == high, exactly 1 element remains to be checked."
            }
          ],
          "analogies": [
            "Closing sliding doors from both sides: low moves right, high moves left until they meet or cross."
          ],
          "common_misconceptions": [
            "Using while (low < high) for standard search, which skips checking the last remaining element.",
            "Updating low = mid, causing an infinite loop when high - low == 1."
          ],
          "visuals": [
            {
              "visual_id": "vis_pointer_trace_table",
              "title": "Step-by-Step Pointer Trace Table",
              "type": "trace_table",
              "content": "| Iteration | Low | High | Mid | Arr[Mid] | Decision | New Low | New High |\n|---|---|---|---|---|---|---|---|\n| 1 | 0 | 4 | 2 | 15 | Target 22 > 15 | 3 | 4 |\n| 2 | 3 | 4 | 3 | 22 | Target 22 == 22 | Found at 3 | - |",
              "caption": "Step-by-step trace showing low, mid, and high pointers during search for 22 in [5, 10, 15, 22, 30]."
            },
            {
              "visual_id": "vis_pointer_ascii",
              "title": "ASCII Pointer Diagram",
              "type": "ascii",
              "content": "Array:  [ 5,  10,  15,  22,  30 ]\nIndex:    0    1    2    3    4\nIter 1:   L         M         H    (15 < 22 -> L = M + 1)\nIter 2:                  L    H    (M = 3: Arr[3] == 22 -> Found!)",
              "caption": "ASCII diagram showing pointer movements across iterations."
            }
          ],
          "question_bank": [
            {
              "question_id": "bs_loop_q1",
              "difficulty_tier": 1,
              "question_type": "conceptual",
              "question": "In standard binary search, why is the loop condition 'while low <= high' rather than 'while low < high'?",
              "expected_answer": "Because when low == high, there is still one valid element in the search space [low, low] that must be inspected.",
              "evaluation_criteria": [
                "Mentions the case where low == high",
                "Explains that a single element remains to be tested"
              ]
            },
            {
              "question_id": "bs_loop_q2",
              "difficulty_tier": 2,
              "question_type": "application",
              "question": "In array [10, 20, 30, 40, 50], if target is 40, what are the values of low, high, and mid in the second iteration?",
              "expected_answer": "Low = 3, High = 4, Mid = 3 (Arr[3] = 40)",
              "evaluation_criteria": [
                "Correctly identifies Low=3, High=4, Mid=3"
              ]
            },
            {
              "question_id": "bs_loop_q3",
              "difficulty_tier": 3,
              "question_type": "application",
              "question": "What happens if you update 'low = mid' instead of 'low = mid + 1' when low = 0 and high = 1 and arr[mid] < target?",
              "expected_answer": "It causes an infinite loop because mid evaluates to 0, setting low back to 0 repeatedly without shrinking the interval.",
              "is_transfer": True,
              "evaluation_criteria": [
                "Identifies infinite loop or failure to terminate",
                "Explains mid = 0 leads to low staying 0"
              ]
            }
          ]
        }
      ]
    },
    {
      "topic_id": "boundary_conditions_and_off_by_one",
      "title": "Boundary Conditions & Off-by-One Traps",
      "description": "Mastering integer overflow in midpoint calculations, empty/single-element bounds, and pointer crossing invariants.",
      "prerequisites": ["loop_invariants_and_implementation"],
      "difficulty": 3,
      "subtopics": [
        {
          "subtopic_id": "bs_overflow_and_bounds",
          "name": "Integer Overflow & Edge Case Handling",
          "description": "Using mid = low + (high - low) // 2 and handling arrays of size 0 and 1.",
          "explanation_outline": [
            "In languages with fixed-size 32-bit integers, (low + high) can overflow if both are large (~2^30).",
            "Writing mid = low + (high - low) // 2 mathematically computes the exact same midpoint without sum overflow.",
            "Empty arrays (len 0) initialize low = 0, high = -1, which terminates immediately before entering the loop."
          ],
          "learning_objectives": [
            "Explain integer overflow in midpoint calculation and apply the safe formula.",
            "Correctly handle edge cases including empty arrays and single-element arrays."
          ],
          "worked_examples": [
            {
              "title": "Overflow Demonstration",
              "problem": "Suppose low = 1,500,000,000 and high = 1,700,000,000 in 32-bit signed integer arithmetic.",
              "step_by_step_solution": [
                "1. low + high = 3,200,000,000 > 2,147,483,647 (INT_MAX).",
                "2. Signed 32-bit addition overflows into a negative number: -1,094,967,296.",
                "3. Dividing by 2 yields a negative index, triggering an index-out-of-bounds crash!",
                "4. Safe formula: high - low = 200,000,000. (high - low) // 2 = 100,000,000.",
                "5. low + 100,000,000 = 1,600,000,000 (correct, no overflow)."
              ],
              "key_takeaway": "Always use low + (high - low) // 2 in lower-level languages to prevent integer overflow."
            },
            {
              "title": "Empty Array Termination",
              "problem": "Trace search in an empty array arr = [] with target 5.",
              "step_by_step_solution": [
                "1. n = len(arr) = 0.",
                "2. low = 0, high = n - 1 = -1.",
                "3. Loop condition low <= high is 0 <= -1, which is False immediately.",
                "4. Returns -1 without accessing arr[0]."
              ],
              "key_takeaway": "Standard initialization naturally handles empty arrays without special guard clauses."
            }
          ],
          "analogies": [
            "Measuring distance between two milestones: instead of adding their mile markers together, measure the gap between them and add half that gap to the starting marker."
          ],
          "common_misconceptions": [
            "Believing integer overflow only happens with arrays containing billions of elements, forgetting indices themselves can be large in binary search on answer spaces."
          ],
          "visuals": [
            {
              "visual_id": "vis_pointer_crossing",
              "title": "Pointer Crossing on Missing Target",
              "type": "ascii",
              "content": "Array: [ 2,  4,  6,  8 ]   Target = 5\n\nStep 1: Low=0, High=3, Mid=1 (Val 4) -> 5 > 4 -> Low = Mid + 1 = 2\nStep 2: Low=2, High=3, Mid=2 (Val 6) -> 5 < 6 -> High = Mid - 1 = 1\n\nResult: High (1) < Low (2)  <-- Pointers Crossed!\nInsertion Point: Low (2) is where 5 should be inserted to preserve sort order.",
              "caption": "Pointer crossing invariant: when search fails, 'low' points to the first element greater than target."
            }
          ],
          "question_bank": [
            {
              "question_id": "bs_edge_q1",
              "difficulty_tier": 1,
              "question_type": "conceptual",
              "question": "Why is 'low + (high - low) // 2' preferred over '(low + high) // 2' in languages like C++ and Java?",
              "expected_answer": "To prevent integer overflow when low + high exceeds the maximum 32-bit signed integer value.",
              "evaluation_criteria": [
                "Mentions integer overflow or exceeding integer limit"
              ]
            },
            {
              "question_id": "bs_edge_q2",
              "difficulty_tier": 2,
              "question_type": "objective",
              "question": "When binary search terminates with low > high after failing to find a target, what does the index 'low' represent geometrically?",
              "expected_answer": "It represents the insertion index where the target would go to keep the array sorted (or the first element greater than target).",
              "evaluation_criteria": [
                "Mentions insertion index or first element greater than target"
              ]
            },
            {
              "question_id": "bs_edge_q3",
              "difficulty_tier": 3,
              "question_type": "application",
              "question": "Suppose an array has all identical elements [7, 7, 7, 7]. How many comparisons does standard binary search take to find 7?",
              "expected_answer": "Only 1 comparison, because mid = 1 or 2 is immediately 7.",
              "is_transfer": True,
              "evaluation_criteria": [
                "Identifies 1 comparison",
                "Explains that mid element is already 7"
              ]
            }
          ]
        }
      ]
    },
    {
      "topic_id": "boundary_and_variants",
      "title": "Boundary Variants: Lower & Upper Bound",
      "description": "Searching in arrays with duplicates: finding the first occurrence (lower bound) and strictly greater element (upper bound).",
      "prerequisites": ["boundary_conditions_and_off_by_one"],
      "difficulty": 3,
      "subtopics": [
        {
          "subtopic_id": "bs_lower_bound",
          "name": "Lower Bound & First Occurrence Invariant",
          "description": "Finding the first index where arr[index] >= target in arrays with duplicate values.",
          "explanation_outline": [
            "In an array with duplicates, standard binary search may land on any copy.",
            "To find the first occurrence (lower_bound), when arr[mid] == target, do NOT terminate.",
            "Instead, keep searching left by setting high = mid - 1, recording mid as a candidate.",
            "Lower bound finds the first element >= target; upper bound finds the first element > target."
          ],
          "learning_objectives": [
            "Distinguish between standard search, lower_bound (>=), and upper_bound (>).",
            "Find the start and end positions of a target in O(log n)."
          ],
          "worked_examples": [
            {
              "title": "First Occurrence with Duplicates",
              "problem": "Find the first occurrence of 4 in [1, 2, 4, 4, 4, 5, 8].",
              "step_by_step_solution": [
                "1. low = 0, high = 6. mid = 3. arr[3] = 4 (match!). Save ans = 3. Continue left: high = mid - 1 = 2.",
                "2. low = 0, high = 2. mid = 1. arr[1] = 2 < 4. low = mid + 1 = 2.",
                "3. low = 2, high = 2. mid = 2. arr[2] = 4 (match!). Save ans = 2. high = mid - 1 = 1.",
                "4. low = 2 > high = 1. Loop ends. First occurrence is at index 2."
              ],
              "key_takeaway": "When mid matches target, storing mid and moving high = mid - 1 guarantees finding the leftmost copy."
            },
            {
              "title": "Counting Frequency in O(log N)",
              "problem": "Count how many times target 4 appears in [1, 2, 4, 4, 4, 5, 8].",
              "step_by_step_solution": [
                "1. Find lower_bound(4): first index >= 4 is index 2.",
                "2. Find upper_bound(4): first index > 4 is index 5 (value 5).",
                "3. Frequency = upper_bound - lower_bound = 5 - 2 = 3 occurrences!"
              ],
              "key_takeaway": "The count of any element in a sorted array is upper_bound(target) - lower_bound(target)."
            }
          ],
          "analogies": [
            "Looking for the very first page of a multi-page chapter in a textbook: once you find a page in that chapter, you keep flipping backward until you hit the chapter title page."
          ],
          "common_misconceptions": [
            "Using standard binary search and then linearly scanning left and right for duplicates, which degrades to O(N) when all elements are duplicates.",
            "Confusing lower_bound (>= target) with upper_bound (> target)."
          ],
          "visuals": [
            {
              "visual_id": "vis_lower_upper_boundary",
              "title": "Lower Bound vs Upper Bound Boundary",
              "type": "ascii",
              "content": "Array:  [ 1,   3,   5,   5,   5,   8,   9 ]\nIndex:    0    1    2    3    4    5    6\n                    ^              ^\n               Lower Bound     Upper Bound\n               (First >= 5)    (First > 5)\n                    |--------------|\n                 Range of 5: [2, 4], Count = 5 - 2 = 3",
              "caption": "Boundary partition showing Lower Bound (index 2) vs Upper Bound (index 5) for target 5."
            }
          ],
          "question_bank": [
            {
              "question_id": "bs_lb_q1",
              "difficulty_tier": 1,
              "question_type": "conceptual",
              "question": "What is the difference between lower_bound(target) and upper_bound(target)?",
              "expected_answer": "lower_bound finds the first element greater than or equal to target (>=), while upper_bound finds the first element strictly greater than target (>).",
              "evaluation_criteria": [
                "Identifies lower bound as first element >= target",
                "Identifies upper bound as first element > target"
              ]
            },
            {
              "question_id": "bs_lb_q2",
              "difficulty_tier": 2,
              "question_type": "objective",
              "question": "In array [10, 20, 20, 20, 30], what is the index returned by lower_bound(20) and upper_bound(20)?",
              "expected_answer": "lower_bound(20) returns index 1; upper_bound(20) returns index 4.",
              "evaluation_criteria": [
                "Lower bound is index 1",
                "Upper bound is index 4"
              ]
            },
            {
              "question_id": "bs_lb_q3",
              "difficulty_tier": 3,
              "question_type": "application",
              "question": "How do you count the occurrences of target x in a sorted array in O(log n) time without linear scanning?",
              "expected_answer": "By computing upper_bound(x) - lower_bound(x).",
              "is_transfer": True,
              "evaluation_criteria": [
                "Specifies upper_bound minus lower_bound"
              ]
            }
          ]
        }
      ]
    },
    {
      "topic_id": "binary_search_on_answer",
      "title": "Binary Search on Answer (Optimization)",
      "description": "Applying binary search to monotonic decision spaces: transforming optimization problems into feasibility checks.",
      "prerequisites": ["boundary_and_variants"],
      "difficulty": 4,
      "subtopics": [
        {
          "subtopic_id": "bs_monotonic_predicate",
          "name": "Monotonic Predicates & Answer-Space Search",
          "description": "Formulating is_possible(mid) functions where answers exhibit FFF...TTT or TTT...FFF monotonicity.",
          "explanation_outline": [
            "Binary search is not limited to searching arrays: it searches ANY monotonic solution space [min_val, max_val].",
            "Define a boolean predicate check(x) that tests if an answer x is feasible.",
            "If check(x) is monotonic (e.g., False for all x < optimal, True for all x >= optimal), we binary search for the transition boundary.",
            "Classic examples: Koko Eating Bananas, Capacity To Ship Packages Within D Days, Painter's Partition."
          ],
          "learning_objectives": [
            "Identify when an optimization problem can be solved with binary search on the answer space.",
            "Formulate a monotonic check(mid) feasibility function."
          ],
          "worked_examples": [
            {
              "title": "Koko Eating Bananas Feasibility",
              "problem": "Piles = [3, 6, 7, 11], H = 8 hours. Find minimum eating speed k.",
              "step_by_step_solution": [
                "1. Range of speeds: min speed = 1, max speed = max(piles) = 11.",
                "2. Feasibility function check(k): hours needed = sum(ceil(pile / k)). Feasible if hours <= H.",
                "3. Try k = 6: ceil(3/6)+ceil(6/6)+ceil(7/6)+ceil(11/6) = 1 + 1 + 2 + 2 = 6 <= 8 (Feasible: True). Try smaller: high = 5.",
                "4. Try k = 3: 1 + 2 + 3 + 4 = 10 > 8 (Infeasible: False). Try larger: low = 4.",
                "5. Try k = 4: 1 + 2 + 2 + 3 = 8 <= 8 (Feasible: True). Minimum speed is 4!"
              ],
              "key_takeaway": "The answer space [1..11] is monotonic in feasibility [F, F, F, T, T, T, T, T, T, T, T]. Binary search finds the first True in O(N log(max_pile))."
            },
            {
              "title": "Square Root Calculation",
              "problem": "Find integer square root of 16 using binary search on answer space [0..16].",
              "step_by_step_solution": [
                "1. low = 0, high = 16. mid = 8. 8 * 8 = 64 > 16 -> high = 7.",
                "2. low = 0, high = 7. mid = 3. 3 * 3 = 9 < 16 -> low = 4, ans = 3.",
                "3. low = 4, high = 7. mid = 5. 5 * 5 = 25 > 16 -> high = 4.",
                "4. low = 4, high = 4. mid = 4. 4 * 4 = 16 == 16 -> Exact match! Return 4."
              ],
              "key_takeaway": "Searching the space of integers [0..x] finds the square root in O(log x) steps."
            }
          ],
          "analogies": [
            "Adjusting water temperature on a single dial: if it's too cold at setting 3 and too hot at setting 7, you binary search the dial to find the perfect threshold."
          ],
          "common_misconceptions": [
            "Thinking binary search only works when given an explicit array in memory, not realizing it applies to continuous or abstract answer ranges."
          ],
          "visuals": [
            {
              "visual_id": "vis_predicate_step",
              "title": "Monotonic Predicate Boundary (False to True)",
              "type": "mermaid",
              "content": "graph LR\n    K1[\"k=1: F\"] --> K2[\"k=2: F\"]\n    K2 --> K3[\"k=3: F\"]\n    K3 -. Boundary .-> K4[\"k=4: T (First Valid)\"]\n    K4 --> K5[\"k=5: T\"]\n    K5 --> K6[\"k=6: T\"]",
              "caption": "Monotonic feasibility transition from False (too slow) to True (valid speed) at minimum k=4."
            }
          ],
          "question_bank": [
            {
              "question_id": "bs_ans_q1",
              "difficulty_tier": 1,
              "question_type": "conceptual",
              "question": "What core condition must the answer space satisfy to apply Binary Search on the Answer?",
              "expected_answer": "The feasibility function must be monotonic (e.g. if answer X is feasible, all answers > X are also feasible).",
              "evaluation_criteria": [
                "Mentions monotonicity or monotonic feasibility condition"
              ]
            },
            {
              "question_id": "bs_ans_q2",
              "difficulty_tier": 2,
              "question_type": "application",
              "question": "When computing integer square root of N, what are the initial boundaries for the binary search answer space?",
              "expected_answer": "low = 0 (or 1) and high = N (or N // 2 for N >= 4).",
              "evaluation_criteria": [
                "Identifies low=0 or 1 and high=N"
              ]
            },
            {
              "question_id": "bs_ans_q3",
              "difficulty_tier": 3,
              "question_type": "application",
              "question": "In 'Koko Eating Bananas' with piles of bananas and H hours, what is the time complexity of binary search on the answer in terms of array size N and maximum pile size M?",
              "expected_answer": "O(N * log M), because each feasibility check inspects N piles and the answer space [1..M] takes log M iterations.",
              "is_transfer": True,
              "evaluation_criteria": [
                "States O(N * log M)",
                "Explains check takes O(N) and binary search takes log M"
              ]
            }
          ]
        }
      ]
    }
  ]
}

# Validate with Pydantic
validated = RichCurriculum.model_validate(curriculum_data)
print("Validation succeeded! Total topics:", len(validated.topics))

target_path = "multi_agent_tutor/data/curriculum/binary_search_curriculum.json"
with open(target_path, "w") as f:
    json.dump(curriculum_data, f, indent=2)
print("Wrote enriched curriculum to:", target_path)

# Also ensure top-level data/curriculum/binary_search_curriculum.json is present
os.makedirs("data/curriculum", exist_ok=True)
with open("data/curriculum/binary_search_curriculum.json", "w") as f:
    json.dump(curriculum_data, f, indent=2)
print("Wrote enriched curriculum copy to: data/curriculum/binary_search_curriculum.json")
