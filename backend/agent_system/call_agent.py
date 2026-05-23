from config import manager as memory_manager,client
from toolbox import ToolBox
from google.genai import types
from utils import calculate_context_usage,offload_to_summary
import json as json_lib
from prompt import AGENT_SYSTEM_PROMPT
from tools import (TOOL_BY_NAME,search_tavily,
        summarize_conversation, summarize_and_store,
        read_toolbox,get_current_time)


# register all tool so the agent can call them


def execute_tool(tool_name: str, tool_args: dict, current_thread_id: str | None = None) -> str:
    """Execute a tool by looking it up in the toolbox."""
     
    if tool_name not in TOOL_BY_NAME:
        return f"Error: Tool '{tool_name}' not found"

    args = dict(tool_args or {})

    # Ensure conversation summarization marks source rows in the active thread.
    if tool_name == "summarize_and_store" and "thread_id" not in args and current_thread_id is not None:
        args["thread_id"] = str(current_thread_id)

    return str(TOOL_BY_NAME[tool_name](**args) or "Done")

def call_gemini_chat(messages: list, tools: list = None, model: str = "gemini-3.5-flash"):
    """Call Gemini Chat generation API with tools."""
    if tools:
        func_tools = types.Tool(function_declarations=tools)
        config = types.GenerateContentConfig(tools=[func_tools],
                                              system_instruction= AGENT_SYSTEM_PROMPT 
                                             )
        res = client.models.generate_content(
            model=model,
            config=config,
            contents=messages
        )
    return res

def call_agent(query: str, thread_id: str = "1", max_iterations: int = 10) -> str:
    """Agent loop with context window monitoring and summarization."""
    thread_id = str(thread_id)
    steps = []
    summaries = []  # Track created summaries
    
    # 1. Build context from memory
    print("\n" + "="*50)
    print("BUILDING CONTEXT...")
    
    # Build memory context (excluding query for now)
    memory_context = ""
    memory_context += memory_manager.read_conversational_memory(thread_id) + "\n\n"
    memory_context += memory_manager.read_knowledge_base(query) + "\n\n"
    memory_context += memory_manager.read_workflow(query) + "\n\n"
    memory_context += memory_manager.read_entity(query) + "\n\n"
    memory_context += memory_manager.read_summary_context(query, thread_id=thread_id) + "\n\n"  # Shows IDs + descriptions (thread-scoped when available)
     
    # Check context usage - summarize if >80%
    usage = calculate_context_usage(memory_context)
    
    if usage['percent'] > 80:
        memory_context, summaries = offload_to_summary(
            memory_context,
            memory_manager,
            thread_id=thread_id,
        )
       
        usage = calculate_context_usage(memory_context)
       
    # Now prepend the query (always preserved, never summarized)
    context = f"# Question\n{query}\n\n{memory_context}"

    
    # Get tools
    dynamic_tools = memory_manager.read_toolbox(query, k=5)
    print("Tools:")
    
    # 4. Store user message & extract entities
    memory_manager.write_conversational_memory(query, "user", thread_id)
    try:
        memory_manager.write_entity("", "", "", llm_client=client, text=query)
    except Exception:
        pass
    
    # Agent loop
    messages = [context]
    final_answer = ""
    
    print("AGENT LOOP")
    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1} ---")
        
        response = call_gemini_chat(messages, tools=dynamic_tools)
        msg = response
        
        if msg.candidates[0].content.parts[0].function_call:
            
            function_call = msg.candidates[0].content.parts[0].function_call
            messages.append(msg.candidates[0].content)
    
            tool_name = function_call.name
            tool_args = function_call.args
            # Format args for display (truncate long values)
            args_display = {k: (v[:50] + '...' if isinstance(v, str) and len(v) > 50 else v) 
                            for k, v in tool_args.items()}
            print(f"{tool_name}")
            
            try:
                result = execute_tool(tool_name, tool_args, current_thread_id=thread_id)
                status = "success"
                error_message = None
                steps.append(f"{tool_name}({args_display}) → success")
            except Exception as e:
                result = f"Error: {e}"
                status = "failed"
                error_message = str(e)
                steps.append(f"{tool_name}({args_display}) → failed")

            # # Persist full tool output to TOOL_LOG_MEMORY
            log_id = memory_manager.write_tool_log(
                thread_id=thread_id,
                tool_call_id=function_call.id,
                tool_name=tool_name,
                tool_args=tool_args,
                result=result,
                status=status,
                error_message=error_message,
                metadata={"iteration": iteration + 1},
            )

            # Next call gets only the immediate tool result (bounded for context control)
            if len(result) > 3000:
                result_for_llm = result[:3000] + f"\n\n[Truncated for context. Full output saved in TOOL_LOG_MEMORY as log_id: {log_id}]"
            else:
                result_for_llm = result
            result_display = result_for_llm[:200] + "..." if len(result_for_llm) > 200 else result_for_llm
            function_response_part = types.Part.from_function_response(
                                            name=tool_name,
                                            response={"result": result_for_llm},
                                        )
            messages.append(types.Content(role="tool", parts=[function_response_part]))
        else:
            final_answer = msg.text or ""
            break
    else:
        # Max iterations reached without final answer
        final_answer = "I was unable to complete your request."
    
    # 6. Save workflow & entities
    if steps:
        memory_manager.write_workflow(query, steps, final_answer)
    try:
        memory_manager.write_entity("", "", "", llm_client=client, text=final_answer)
    except Exception:
        pass
    memory_manager.write_conversational_memory(final_answer, "assistant", thread_id)
    return final_answer


