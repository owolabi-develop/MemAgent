import uuid
MODEL_TOKEN_LIMITS = {
    "gemini-3.5-flash": 256000,
}

from .config import manager as memory_manager,client

# Context window calculator - returns percentage used
def calculate_context_usage(context: str, model: str = "gemini-3.5-flash") -> dict:
    """Calculate context window usage as percentage."""
    estimated_tokens = len(context) // 4  # ~4 chars per token
    max_tokens = MODEL_TOKEN_LIMITS.get(model, 128000)
    percentage = (estimated_tokens / max_tokens) * 100
    return {"tokens": estimated_tokens, "max": max_tokens, "percent": round(percentage, 1)}




def summarise_context_window(content: str, memory_manager,model: str = "gemini-3.5-flash") -> dict:
    """
    Summarise content using an LLM and store in summary memory.
    """
    cleaned = (content or "").strip()
    if not cleaned:
        return {"status": "nothing_to_summarize"}

    def _message_text(resp) -> str:
        msg = resp.text.strip()
       
        return msg

    summary_prompt = f"""You are creating durable memory for an AI research assistant.
Summarize this conversation so it can be resumed accurately later.

Output with exactly these headings:
### Technical Information
### Emotional Context
### Entities & References
### Action Items & Decisions

Rules:
- Keep concrete details (names, dates, APIs, errors, decisions).
- Separate confirmed facts from open questions where relevant.
- Do not invent information.
- Keep it concise and useful for continuation.

Conversation:
{cleaned[:6000]}"""
   
    response = client.models.generate_content(
        model=model,
        contents=summary_prompt,
    )
    summary = _message_text(response)

    # Retry once with a simpler prompt if output is empty.
    if not summary:
        retry_prompt = f"""Summarize this conversation in <= 180 words using these headings:
### Technical Information
### Emotional Context
### Entities & References
### Action Items & Decisions

Conversation:
{cleaned[:6000]}"""
        retry = client.models.generate_content(
            model=model,
            messages=retry_prompt,
        )
        summary = _message_text(retry)

    if not summary:
        excerpt = cleaned[:500].replace("\n", " ").strip()
        summary = (
            "### Technical Information\n"
            f"{excerpt or '(No content provided.)'}\n\n"
            "### Emotional Context\n"
            "Not available from model output.\n\n"
            "### Entities & References\n"
            "Not available from model output.\n\n"
            "### Action Items & Decisions\n"
            "Not available from model output."
        )

    desc_prompt = f"""Create a short 8-12 word label for this summary.
Return ONLY the label.

Summary:
{summary}"""

    desc_response = client.models.generate_content(
        model=model,
        messages=desc_prompt,
    )
    description = _message_text(desc_response) or "Conversation summary"

    summary_id = str(uuid.uuid4())[:8]
    memory_manager.write_summary(summary_id, cleaned, summary, description)

    return {"id": summary_id, "description": description, "summary": summary}





def summarize_conversation(thread_id: str) -> dict:
    """
    Summarize all unsummarized messages in a thread and mark those exact units.

    This function:
    1. Reads unsummarized message rows from the thread
    2. Generates a structured summary via LLM
    3. Stores the summary in summary memory
    4. Marks the exact source rows with summary_id
    5. Returns the summary object for continued context
    """
    thread_id = str(thread_id)

    # Read raw unsummarized conversation units (IDs + content)
    with memory_manager.conn.cursor() as cur:
        cur.execute(f"""
            SELECT id, role, content, con_timestamp
            FROM {memory_manager.conversation_table}
            WHERE thread_id = %s AND summary_id IS NULL
            ORDER BY con_timestamp ASC
        """, {"thread_id": thread_id})
        rows = cur.fetchall()

    if not rows:
        return {"status": "nothing_to_summarize"}

    # Build transcript from unsummarized units only
    message_ids = []
    transcript_lines = []
    for msg_id, role, content, timestamp in rows:
        message_ids.append(msg_id)
        ts_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else "Unknown"
        transcript_lines.append(f"[{ts_str}] [{str(role).upper()}] {content}")

    transcript = "\n".join(transcript_lines)

    # Summarize the exact transcript
    result = summarise_context_window(transcript, memory_manager)
    if result.get("status") == "nothing_to_summarize":
        return result

    summary_id = result["id"]

    # Mark the exact source rows with the generated summary_id
    with memory_manager.conn.cursor() as cur:
        cur.executemany(f"""
            UPDATE {memory_manager.conversation_table}
            SET summary_id = %s
            WHERE id = %s AND summary_id IS NULL
        """, [{"summary_id": summary_id, "id": msg_id} for msg_id in message_ids])
    memory_manager.conn.commit()

    result["num_messages_summarized"] = len(message_ids)

    return result


def monitor_context_window(context: str, model: str = "gpt-5-mini") -> dict:
    """
    Monitor the current context window and return capacity utilization.

    Args:
        context: The current context string to measure
        model: The model being used (to determine max tokens)

    Returns:
        dict with:
        - tokens: Estimated token count
        - max: Maximum tokens for the model
        - percent: Percentage of capacity used
        - status: 'ok', 'warning', or 'critical' based on usage
    """
    result = calculate_context_usage(context, model)

    # Add status indicator
    if result['percent'] < 50:
        result['status'] = 'ok'
    elif result['percent'] < 80:
        result['status'] = 'warning'
    else:
        result['status'] = 'critical'

    return result


def offload_to_summary(context: str, memory_manager,thread_id: str = None) -> tuple:
    """
    Simple context compaction:
    - If thread_id is provided, summarize unsummarized conversation units for that thread.
    - Otherwise, summarize the provided context string.
    - Replace only conversation-heavy context and keep other memory segments.
    """
    raw_context = (context or "").strip()

    if thread_id:
        result = summarize_conversation(thread_id)
    else:
        result = summarise_context_window(raw_context, memory_manager)

    if result.get("status") == "nothing_to_summarize":
        return raw_context, []

    summary_ref = f"[Summary ID: {result['id']}] {result['description']}"
    conversation_stub = (
        "## Conversation Memory\n"
        "Older conversation content was summarized to reduce context size.\n"
        "Use Summary Memory references + expand_summary(id) for full detail."
    )

    # Replace only conversation section, preserve other memory sections.
    compact_context = raw_context
    if "## Conversation Memory" in compact_context:
        lines = compact_context.splitlines()
        rebuilt = []
        in_conversation = False
        inserted_stub = False

        for line in lines:
            if line.startswith("## "):
                heading = line.strip()
                if heading == "## Conversation Memory":
                    in_conversation = True
                    if not inserted_stub:
                        if rebuilt and rebuilt[-1].strip():
                            rebuilt.append("")
                        rebuilt.extend(conversation_stub.splitlines())
                        rebuilt.append("")
                        inserted_stub = True
                    continue
                in_conversation = False

            if not in_conversation:
                rebuilt.append(line)

        compact_context = "\n".join(rebuilt).strip()
    else:
        compact_context = f"{conversation_stub}\n\n{compact_context}".strip()

    if "## Summary Memory" in compact_context:
        compact_context = f"{compact_context}\n{summary_ref}".strip()
    else:
        compact_context = (
            f"{compact_context}\n\n"
            "## Summary Memory\n"
            "Use expand_summary(id) to retrieve full underlying content.\n"
            f"{summary_ref}"
        ).strip()

    return compact_context, [result]

 