import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Bot, User, SendHorizontal, Loader2,RotateCcw} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { loadConversationHistory, chatAgent } from "../lib/agent.api";

const queryClient = new QueryClient();

export const ChatAgent = () => (
  <QueryClientProvider client={queryClient}>
    <ChatAgentInner />
  </QueryClientProvider>
);

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

interface ConversationHistory {
  conversation_history: Message[];
}

const ChatAgentInner = () => {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  // null = not yet mounted, false = ready to fetch, true = fetch done
  const [fetchHistory, setFetchHistory] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Fires once on mount — enabled starts true, flips off after data arrives
  const { data: historyData, isLoading } = useQuery<ConversationHistory>({
    queryKey: ["conversation-history"],
    queryFn: loadConversationHistory,
    enabled: fetchHistory,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  // Seed messages from history — runs once when data first arrives
  useEffect(() => {
    if (historyData) {
      setMessages(historyData.conversation_history ?? []);
      setFetchHistory(false); // close the gate so query never runs again on its own
    }
  }, [historyData]);

  // Open the gate on mount — only ever runs once
  useEffect(() => {
    setFetchHistory(true);
  }, []);

  const { mutate: sendMessage, isPending } = useMutation({
    mutationFn: (query: string) => chatAgent({ query }),
    onMutate: (query: string) => {
      // Append user message immediately while waiting for response
      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: "user",
        content: query,
        created_at: new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, userMsg]);
    },
    onSuccess: (response) => {
      if (response?.response) {
        // Append assistant reply — then open gate to re-fetch history from backend
        const assistantMsg: Message = {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: response.response,
          created_at: new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }),
        };
        setMessages((prev) => [...prev, assistantMsg]);
        // History re-fetch only triggers AFTER chat response is received
        setFetchHistory(true);
      }
    },
    onError: () => {
      // Roll back the last optimistic user message
      setMessages((prev) => {
        const idx = [...prev].reverse().findIndex((m) => m.role === "user");
        if (idx === -1) return prev;
        const realIdx = prev.length - 1 - idx;
        return prev.filter((_, i) => i !== realIdx);
      });
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isPending]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isPending) return;
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    sendMessage(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50 font-sans">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 bg-white border-b border-gray-200">
        <div className="flex items-center gap-2.5">
          <div className="relative w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
            <Bot size={16} className="text-blue-600" />
            <span className="absolute -bottom-0.5 -right-0.5 w-2 h-2 bg-green-500 rounded-full border-2 border-white" />
          </div>
          <div>
            <p className="text-[13px] font-medium text-gray-900 leading-none">Assistant</p>
            <p className="text-[11px] text-gray-400 mt-0.5">
              {isLoading ? "Loading…" : "Online now"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          
          <button
            onClick={() => setMessages([])}
            className="w-7 h-7 flex items-center justify-center rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
          >
            <RotateCcw size={15} />
          </button>
        
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4">
        {isLoading && (
          <div className="flex justify-center items-center gap-2 py-10 text-gray-400 text-sm">
            <Loader2 size={14} className="animate-spin" />
            Loading conversation…
          </div>
        )}

        {!isLoading && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center min-h-[40vh] gap-3 text-center">
            <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center">
              <Bot size={18} className="text-blue-500" />
            </div>
            <p className="text-sm text-gray-400 max-w-xs">Start a conversation. Ask anything.</p>
          </div>
        )}

        {messages.map((msg, i) => {
          const isUser = msg.role === "user";
          return (
            <div key={msg.id ?? i} className={`flex items-end gap-2.5 ${isUser ? "flex-row-reverse" : ""}`}>
              <div className={`flex-shrink-0 w-6 h-6 rounded-md flex items-center justify-center ${
                isUser ? "bg-gray-100 border border-gray-200" : "bg-blue-50"
              }`}>
                {isUser
                  ? <User size={12} className="text-gray-500" />
                  : <Bot size={12} className="text-blue-600" />
                }
              </div>
              <div className={`flex flex-col gap-1 max-w-[72%] ${isUser ? "items-end" : ""}`}>
                <div className={`text-[13px] leading-relaxed px-3.5 py-2.5 ${
                  isUser
                    ? "bg-blue-50 text-blue-900 rounded-[10px] rounded-br-[2px]"
                    : "bg-white border border-gray-200 text-gray-800 rounded-[10px] rounded-bl-[2px]"
                }`}>
                  {isUser
                    ? msg.content
                    : <ReactMarkdown>{msg.content}</ReactMarkdown>
                  }
                </div>
                <span className="text-[10px] text-gray-400 px-1">{msg.created_at}</span>
              </div>
            </div>
          );
        })}

        {isPending && (
          <div className="flex items-end gap-2.5">
            <div className="flex-shrink-0 w-6 h-6 rounded-md bg-blue-50 flex items-center justify-center">
              <Bot size={12} className="text-blue-600" />
            </div>
            <div className="bg-white border border-gray-200 rounded-[10px] rounded-bl-[2px] px-3.5 py-3">
              <div className="flex gap-1 items-center">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-gray-300 animate-bounce"
                    style={{ animationDelay: `${i * 160}ms`, animationDuration: "1.1s" }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input — pill style */}
      <div className="px-4 pb-4 pt-2 border-t border-gray-100">
        <div className={`flex items-center gap-2 rounded-full px-4 py-2 bg-gray-100 border transition-all ${
          input ? "border-gray-400 bg-white" : "border-transparent"
        }`}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="Type a message…"
            rows={1}
            className="flex-1 text-[13px] text-gray-900 placeholder-gray-400 bg-transparent resize-none outline-none leading-[1.45] max-h-[80px] py-1"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isPending}
            className="flex-shrink-0 w-7 h-7 rounded-full bg-gray-900 disabled:opacity-25 disabled:cursor-not-allowed flex items-center justify-center transition-all hover:opacity-75 active:scale-90"
          >
            {isPending
              ? <Loader2 size={12} className="animate-spin text-white" />
              : <SendHorizontal size={12} className="text-white" />
            }
          </button>
        </div>
        
      </div>
    </div>
  );
};