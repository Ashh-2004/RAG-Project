import React, { useState, useEffect } from 'react';
import Sidebar, { DEFAULT_EMPLOYEES } from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import { sendChatMessage, checkBackendHealth, fetchEmployees } from './services/api';

export default function App() {
  const [employeesList, setEmployeesList] = useState(DEFAULT_EMPLOYEES);
  const [selectedEmp, setSelectedEmp] = useState(DEFAULT_EMPLOYEES[0]); // Default to General
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [serverOnline, setServerOnline] = useState(true);

  // Check backend health & fetch live employee profiles on mount
  useEffect(() => {
    verifyHealthAndEmployees();
    const interval = setInterval(verifyHealthAndEmployees, 10000);
    return () => clearInterval(interval);
  }, []);

  const verifyHealthAndEmployees = async () => {
    const isHealthy = await checkBackendHealth();
    setServerOnline(isHealthy);

    if (isHealthy) {
      const liveData = await fetchEmployees();
      if (liveData && liveData.length > 0) {
        setEmployeesList(liveData);
        setSelectedEmp((prev) => {
          if (prev.isGeneral || !prev.emp_id) return prev;
          const match = liveData.find((e) => e.emp_id === prev.emp_id);
          return match ? { ...prev, ...match } : prev;
        });
      }
    }
  };

  const handleSendMessage = async (promptText) => {
    if (!promptText.trim()) return;

    setError(null);
    const userMsgId = Date.now().toString();

    // 1. Append User Message
    const userMessage = {
      id: userMsgId,
      sender: 'user',
      text: promptText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    const updatedHistory = [...messages, userMessage];
    setMessages(updatedHistory);
    setIsLoading(true);

    try {
      // 2. Call FastAPI Backend Endpoint with History
      const response = await sendChatMessage(promptText, selectedEmp.emp_id, updatedHistory);

      // 3. Append Assistant Message with metadata badges
      const botMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: response.answer,
        sources: response.sources || [],
        tools_used: response.tools_used || [],
        agent_routed: response.agent_routed || 'EmployeeMate',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setMessages((prev) => [...prev, botMessage]);

      // 4. Real-time update of employee profiles & leave balances
      if (response.updated_employees) {
        setEmployeesList(response.updated_employees);
        const match = response.updated_employees.find((e) => e.emp_id === selectedEmp.emp_id);
        if (match) {
          setSelectedEmp(match);
        }
      } else {
        verifyHealthAndEmployees();
      }
    } catch (err) {
      console.error('Failed to send message:', err);
      setError(`Failed to reach AI Assistant: ${err.message}. Make sure FastAPI is running at .`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setError(null);
  };

  return (
    <div className="flex h-screen w-screen bg-[#fcf5eb] text-[#1c1e21] font-sans overflow-hidden">
      {/* Sidebar Profile Switcher */}
      <Sidebar
        employees={employeesList}
        selectedEmp={selectedEmp}
        onSelectEmp={(emp) => {
          setSelectedEmp(emp);
          setError(null);
        }}
        onSendQuickPrompt={handleSendMessage}
        serverOnline={serverOnline}
        onRefreshHealth={verifyHealthAndEmployees}
      />

      {/* Main Conversational Window */}
      <ChatWindow
        messages={messages}
        selectedEmp={selectedEmp}
        isLoading={isLoading}
        error={error}
        onSendMessage={handleSendMessage}
        onClearChat={handleClearChat}
        onSendQuickPrompt={handleSendMessage}
      />
    </div>
  );
}
