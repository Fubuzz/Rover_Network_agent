# Crews Documentation

This document describes the CrewAI crews that orchestrate agent workflows.

## Overview

Crews coordinate multiple agents to complete complex tasks. Each crew defines:
- Which agents participate
- Task sequences
- Process flow (sequential or hierarchical)
- Inter-agent communication

## Crew Types

### 1. Contact Crew

**Purpose**: Manage contact operations with validation and classification

**Agents**:
- Contact Management Agent (primary)
- Classification Agent
- Evaluation Agent

**Workflows**:

#### Add Contact
```
1. Input received
2. Contact Agent validates data
3. Contact Agent stores in Google Sheets
4. Classification Agent assigns category
5. Evaluation Agent checks quality
6. Return result
```

#### Update Contact
```
1. Find existing contact
2. Apply updates
3. Validate changes
4. Store updated record
5. Return result
```

#### View Contact
```
1. Retrieve contact by name
2. Format for display
3. Return contact card
```

#### Delete Contact
```
1. Find contact
2. Remove from sheet
3. Log deletion
4. Return confirmation
```

---

### 2. Enrichment Crew

**Purpose**: Research and enrich contact data

**Agents**:
- Enrichment Agent (primary)
- Evaluation Agent
- Troubleshooting Agent

**Workflows**:

#### Enrich Contact
```
1. Retrieve existing contact data
2. Search web for additional info
3. Parse search results
4. Validate new data
5. Update contact record
6. Return enrichment report
```

#### Research Company
```
1. Search for company information
2. Find LinkedIn company page
3. Gather recent news
4. Compile company profile
5. Return research report
```

#### Find LinkedIn
```
1. Search for LinkedIn profile
2. Validate URL
3. Return profile link
```

---

### 3. Input Processing Crew

**Purpose**: Process various input formats

**Agents**:
- Input Processing Agent (primary)
- Contact Management Agent
- Evaluation Agent

**Workflows**:

#### Process Text
```
1. Parse natural language
2. Extract contact fields
3. Validate extracted data
4. Add to contacts
5. Classify contact
6. Return result
```

#### Process Voice
```
1. Receive transcript
2. Parse for contact info
3. Handle ambiguities
4. Add to contacts
5. Return result
```

#### Process Image
```
1. Receive OCR result
2. Parse structured data
3. Validate fields
4. Add to contacts
5. Return result
```

#### Process Bulk
```
1. Parse CSV/text file
2. Extract multiple contacts
3. Validate each contact
4. Import to sheet
5. Return import summary
```

---

### 4. Reporting Crew

**Purpose**: Generate reports and analytics

**Agents**:
- Reporting Agent (primary)
- Evaluation Agent

**Workflows**:

#### Generate Statistics
```
1. Query all contacts
2. Calculate totals
3. Group by attributes
4. Format statistics
5. Return report
```

#### Generate Report
```
1. Retrieve contact data
2. Gather all related info
3. Format detailed report
4. Return report
```

#### Network Insights
```
1. Analyze all contacts
2. Identify patterns
3. Calculate metrics
4. Generate insights
5. Return analysis
```

## Crew Execution

### Sequential Process

Most crews use sequential processing:

```python
crew = Crew(
    agents=[agent1, agent2, agent3],
    tasks=[task1, task2, task3],
    process=Process.sequential
)
```

Tasks execute in order, with each task's output available to the next.

### Hierarchical Process

For complex operations:

```python
crew = Crew(
    agents=[manager, worker1, worker2],
    tasks=[main_task],
    process=Process.hierarchical,
    manager_agent=manager
)
```

Manager delegates subtasks to workers.

## Creating Custom Crews

1. Create crew file in `crews/`:

```python
from crewai import Crew, Task, Process
from agents.my_agent import get_my_agent

class MyCrew:
    def __init__(self):
        self.agent = get_my_agent()
    
    def my_workflow(self, input_data: str) -> str:
        task = Task(
            description=f"Process this: {input_data}",
            agent=self.agent,
            expected_output="Processed result"
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            process=Process.sequential
        )
        
        result = crew.kickoff()
        return str(result)
```

2. Add getter function:

```python
_my_crew = None

def get_my_crew():
    global _my_crew
    if _my_crew is None:
        _my_crew = MyCrew()
    return _my_crew
```

3. Use in handlers

## Best Practices

1. **Task Specificity**: Clear, specific task descriptions
2. **Expected Output**: Define what success looks like
3. **Error Handling**: Wrap crew execution in try/except
4. **Logging**: Track crew activities for debugging
5. **Context Passing**: Use task outputs for inter-task communication

## Performance Considerations

- Crews add overhead; use for complex operations only
- Sequential process is faster for simple workflows
- Consider caching frequently used results
- Monitor API usage (each agent interaction costs tokens)
