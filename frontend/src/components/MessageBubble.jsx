import React from 'react';
import { Bot, User, Wrench, FileText, Cpu, Check, Copy, CheckCheck } from 'lucide-react';

export default function MessageBubble({ message, currentUser }) {
  const [copied, setCopied] = React.useState(false);
  const isUser = message.sender === 'user';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Helper for agent badge styling
  const getAgentBadgeStyle = (agentName) => {
    switch (agentName) {
      case 'KnowledgeAgent':
        return {
          label: 'Knowledge Agent (RAG)',
          className: 'bg-[#0373e9]/10 text-[#0373e9] border-[#0373e9]/30'
        };
      case 'HRAgent':
        return {
          label: 'HR Specialist Agent',
          className: 'bg-[#25d366]/15 text-[#111b21] border-[#25d366]/30'
        };
      case 'Orchestrator_MultiAgent':
        return {
          label: 'Multi-Agent Orchestrator',
          className: 'bg-purple-100 text-purple-800 border-purple-200'
        };
      default:
        return {
          label: agentName || 'System Agent',
          className: 'bg-[#f0f4f9] text-[#1c1e21] border-[#d8c7b5]'
        };
    }
  };

  return (
    <div className={`flex items-start space-x-3 my-3 max-w-4xl ${isUser ? 'ml-auto flex-row-reverse space-x-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs flex-shrink-0 shadow-sm ${
        isUser
          ? 'bg-[#25d366] text-white'
          : 'bg-white border border-[#f0f4f9] text-[#1c1e21]'
      }`}>
        {isUser ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-[#25d366]" />}
      </div>

      {/* Bubble Box */}
      <div className={`flex flex-col space-y-1.5 max-w-[85%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`p-4 rounded-[12px] text-sm leading-relaxed relative group shadow-sm border whitespace-pre-wrap break-words ${
          isUser
            ? 'bg-[#d9fdd3] text-[#111b21] border-[#bbf2b3] bubble-outgoing'
            : 'bg-white text-[#1c1e21] border-[#f0f4f9] bubble-incoming'
        }`}>
          {/* Main Message Text */}
          <div className="whitespace-pre-wrap break-words font-sans">
            {message.text && message.text.trim() ? (
              message.text
            ) : (
              <span className="text-[#5e5e5e] italic text-xs"></span>
            )}
          </div>

          {/* Copy Button */}
          {!isUser && (
            <button
              onClick={handleCopy}
              className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 p-1.5 rounded-full bg-[#f0f4f9] hover:bg-[#e4ebf3] text-[#5e5e5e] hover:text-[#1c1e21] transition-all"
              title="Copy answer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-[#25d366]" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          )}

          {/* Timestamp inline footer */}
          <div className={`flex items-center justify-end space-x-1 text-[11px] text-[#5e5e5e] mt-1 pt-1 ${isUser ? 'border-t border-[#bbf2b3]/50' : 'border-t border-[#f0f4f9]'}`}>
            <span>{message.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            {isUser && <CheckCheck className="w-3.5 h-3.5 text-[#25d366] inline" />}
          </div>
        </div>

        {/* Assistant Rich Metadata Badges */}
        {!isUser && (message.agent_routed || (message.tools_used && message.tools_used.length > 0) || (message.sources && message.sources.length > 0)) && (
          <div className="flex flex-wrap gap-2 pt-0.5 text-xs">
            {/* 1. Agent Routing Badge */}
            {message.agent_routed && (
              <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-[50px] border font-medium ${getAgentBadgeStyle(message.agent_routed).className}`}>
                <Cpu className="w-3 h-3" />
                Routed via: {getAgentBadgeStyle(message.agent_routed).label}
              </span>
            )}

            {/* 2. Tool Execution Badges */}
            {message.tools_used && message.tools_used.map((tool, idx) => (
              <span key={idx} className="inline-flex items-center gap-1 px-3 py-1 rounded-[50px] bg-amber-50 text-amber-800 border border-amber-200 font-medium">
                <Wrench className="w-3 h-3 text-amber-600" />
                Executed: <code className="font-mono text-[11px]">{tool}</code>
              </span>
            ))}

            {/* 3. Document Sources Badges */}
            {message.sources && message.sources.map((src, idx) => (
              <span key={idx} className="inline-flex items-center gap-1 px-3 py-1 rounded-[50px] bg-[#0373e9]/10 text-[#0373e9] border border-[#0373e9]/20 font-medium">
                <FileText className="w-3 h-3" />
                Source: <span className="font-mono text-[11px]">{src}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
