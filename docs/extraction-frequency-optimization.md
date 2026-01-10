# Extraction Frequency Optimization

## Overview

This document outlines a future optimization opportunity for the profile extraction service. Currently, profile extraction runs on **every message**, which adds ~$0.001-0.002 per message exchange. By reducing extraction frequency, we can save 75-90% of extraction costs.

## Current Implementation

**Location:** `src/services/profile_extraction_service.py`
**Called from:** `src/api/routes/conversations.py:send_message()`

```python
# Current: Extracts after EVERY message
extraction_result = await extraction_service.extract_and_update(
    conversation_id=conversation_id,
    session_id=session_id,
    profile_id=profile_id,
)
```

### Current Cost Impact
- Model: `gpt-4o-mini` (already optimized from gpt-4o)
- Input tokens per call: ~1,100 (system prompt + 10 messages)
- Output tokens per call: ~350 (JSON response)
- Cost per extraction: ~$0.0006-0.001
- 10-message conversation: ~$0.006-0.01 extraction cost

## Proposed Optimization Strategies

### Strategy 1: Extract Every N Messages (Recommended)

Extract only every 3-5 messages instead of every message.

**Implementation:**

```python
# In conversations.py send_message()

# Get current message count
conv_service = ConversationService()
messages = await conv_service.get_recent_messages(conversation_id, limit=100)
message_count = len(messages)

# Extract every 3 messages (including first message)
EXTRACTION_INTERVAL = 3
should_extract = message_count == 1 or message_count % EXTRACTION_INTERVAL == 0

if should_extract:
    extraction_result = await extraction_service.extract_and_update(...)
```

**Pros:**
- Simple to implement
- Predictable extraction pattern
- 67-80% reduction in extraction calls

**Cons:**
- May miss time-sensitive data mentioned in skipped messages
- Slightly delayed profile updates

**Cost savings:** ~$0.004-0.008 per 10-message conversation

### Strategy 2: Phase Change + Periodic Extraction

Extract only on phase changes plus periodic backup extractions.

**Implementation:**

```python
# In conversations.py send_message()

# Check if phase changed
previous_phase = conversation.get("metadata", {}).get("last_extraction_phase")
current_phase = conversation["phase"]
phase_changed = previous_phase != current_phase

# Also extract periodically (every 5 messages since last extraction)
last_extraction_msg = conversation.get("metadata", {}).get("last_extraction_msg_count", 0)
messages_since_extraction = message_count - last_extraction_msg

should_extract = phase_changed or messages_since_extraction >= 5

if should_extract:
    extraction_result = await extraction_service.extract_and_update(...)
    # Update conversation metadata
    await conv_service.update_conversation(conversation_id, {
        "metadata": {
            **conversation.get("metadata", {}),
            "last_extraction_phase": current_phase,
            "last_extraction_msg_count": message_count,
        }
    })
```

**Pros:**
- Captures critical moments (phase transitions)
- More intelligent extraction timing
- 70-90% reduction in extraction calls

**Cons:**
- More complex implementation
- Requires conversation metadata updates

**Cost savings:** ~$0.005-0.009 per 10-message conversation

### Strategy 3: Content-Based Trigger

Extract only when user messages contain extractable content (numbers, company names, etc.).

**Implementation:**

```python
import re

EXTRACTION_TRIGGERS = [
    r'\d+\s*(sqft|square feet|sq ft)',  # Square footage
    r'\$\d+',  # Dollar amounts
    r'\d+\s*(courts?|rooms?)',  # Facility counts
    r'\d+\s*(hours?|minutes?)',  # Time durations
    r'(inc|llc|corp|company|club)\b',  # Company names
]

def should_extract(message: str) -> bool:
    message_lower = message.lower()
    return any(re.search(pattern, message_lower, re.IGNORECASE)
               for pattern in EXTRACTION_TRIGGERS)
```

**Pros:**
- Most intelligent extraction timing
- Only extracts when there's likely new data
- 60-85% reduction in extraction calls

**Cons:**
- Risk of missing data if patterns are incomplete
- Requires pattern maintenance
- More complex debugging

**Cost savings:** Variable, ~$0.004-0.008 per 10-message conversation

## Recommended Approach

**Start with Strategy 1 (Every 3 Messages)** for its simplicity and predictable savings.

### Implementation Steps

1. Add extraction interval constant to config:
   ```python
   # src/core/config.py
   extraction_interval: int = Field(default=3, description="Extract profile every N messages")
   ```

2. Modify `send_message()` in `conversations.py`:
   ```python
   # Check if we should extract
   messages = await conv_service.get_recent_messages(conversation_id, limit=100)
   message_count = len(messages)

   should_extract = (
       message_count == 1 or  # Always extract first message
       message_count % settings.extraction_interval == 0
   )

   if should_extract:
       extraction_result = await extraction_service.extract_and_update(...)
   ```

3. Add final extraction on conversation completion (if applicable)

4. Monitor extraction quality via logs

## Monitoring

Track these metrics after implementation:

1. **Extraction coverage:** % of profile fields populated at conversation end
2. **Extraction latency:** Impact on message response time
3. **Cost per conversation:** Total extraction cost / conversation count
4. **Data freshness:** Time between data mention and extraction

## Risk Mitigation

1. **Always extract on first message** - Captures initial company/context info
2. **Always extract before checkout** - Ensures ROI data is current
3. **Log skipped extractions** - Debug data gaps if needed
4. **A/B test** - Compare extraction quality before full rollout

## Future Considerations

1. **Async extraction queue:** Move extraction to background job for faster responses
2. **Incremental extraction:** Only extract new messages, not full context
3. **Extraction caching:** Skip if no new user messages since last extraction
4. **Model fine-tuning:** Train smaller model specifically for extraction task

## Cost Summary

| Strategy | Extractions per 10 msgs | Cost per 10 msgs | Savings |
|----------|------------------------|------------------|---------|
| Current (every msg) | 10 | ~$0.008 | baseline |
| Every 3 messages | 4 | ~$0.003 | 62% |
| Every 5 messages | 2 | ~$0.002 | 75% |
| Phase change only | ~2-3 | ~$0.002 | 75% |

Combined with existing optimizations (sales knowledge caching, gpt-4o-mini), the total per-message cost can be reduced from ~$0.016 to ~$0.004-0.005.
