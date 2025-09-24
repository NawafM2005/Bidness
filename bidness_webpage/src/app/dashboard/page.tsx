'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';

interface Message {
  sid: string;
  body: string;
  from: string;
  to: string;
  direction: string;
  date_sent: string;
  status: string;
}

interface Conversation {
  [phoneNumber: string]: Message[];
}

export default function Dashboard() {
  const [conversations, setConversations] = useState<Conversation>({});
  const [selectedContact, setSelectedContact] = useState<string>('');
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const router = useRouter();

  const fetchMessages = useCallback(async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'https://bidness.onrender.com'}/api/messages`);
      const data = await response.json();
      
      if (data.success) {
        setConversations(data.conversations);
        // Auto-select first conversation if none selected, but only from active conversations (those with replies)
        const activeConversations = Object.keys(data.conversations).filter((contact) => {
          const messages = data.conversations[contact];
          return messages.some((message: Message) => message.direction === 'inbound');
        });
        
        if (!selectedContact && activeConversations.length > 0) {
          setSelectedContact(activeConversations[0]);
        } else if (selectedContact) {
          // Check if currently selected contact is still active, if not clear selection
          const selectedMessages = data.conversations[selectedContact];
          if (selectedMessages) {
            const hasInboundMessage = selectedMessages.some((message: Message) => message.direction === 'inbound');
            if (!hasInboundMessage) {
              setSelectedContact('');
            }
          }
        }
      }
    } catch (error) {
      console.error('Failed to fetch messages:', error);
    } finally {
      setLoading(false);
    }
  }, [selectedContact]);

  useEffect(() => {
    // Check if user is authenticated
    const isAuthenticated = localStorage.getItem('isAuthenticated');
    if (!isAuthenticated) {
      router.push('/');
      return;
    }

    fetchMessages();
  }, [router, fetchMessages]);

  const sendMessage = async () => {
    if (!newMessage.trim() || !selectedContact) return;

    setSending(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'https://bidness.onrender.com'}/api/send-message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          to: selectedContact,
          body: newMessage,
        }),
      });

      const data = await response.json();
      
      if (data.success) {
        // Immediately add the sent message to the conversation
        const sentMessage: Message = {
          sid: data.sid || `temp_${Date.now()}`,
          body: newMessage,
          from: '+18449870830', // Your Twilio number (should match TWILIO_FROM in backend)
          to: selectedContact,
          direction: 'outbound',
          date_sent: new Date().toISOString(),
          status: 'sent'
        };

        // Update conversations state immediately
        setConversations(prev => ({
          ...prev,
          [selectedContact]: [...(prev[selectedContact] || []), sentMessage]
        }));

        setNewMessage('');
        
        // Still refresh to get any updates from server
        setTimeout(() => {
          fetchMessages();
        }, 1000);
      } else {
        alert('Failed to send message: ' + data.message);
      }
    } catch (error) {
      alert('Failed to send message: ' + error);
    } finally {
      setSending(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('isAuthenticated');
    router.push('/');
  };

  const handleContactSelect = (contact: string) => {
    setSelectedContact(contact);
    setIsMobileMenuOpen(false); // Close mobile menu when contact is selected
  };

  const formatPhoneNumber = (phone: string) => {
    // Format phone number for display
    if (phone.startsWith('+1')) {
      const number = phone.slice(2);
      return `(${number.slice(0, 3)}) ${number.slice(3, 6)}-${number.slice(6)}`;
    }
    return phone;
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const truncateMessage = (message: string, wordLimit: number = 5) => {
    const words = message.split(' ');
    if (words.length > wordLimit) {
      return words.slice(0, wordLimit).join(' ') + '...';
    }
    return message;
  };

  const isUnreadConversation = (messages: Message[]) => {
    // Check if the last message is inbound (received) - meaning we haven't replied yet
    const lastMessage = messages[messages.length - 1];
    return lastMessage && lastMessage.direction === 'inbound';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-200 via-purple-100 to-blue-200 flex items-center justify-center">
        <div className="text-center">
          {/* Spinning Sonal image */}
          <div className="mb-8">
            <div className="w-32 h-32 mx-auto animate-spin">
              <Image
                src="/sonal.png"
                alt="Sonal Avatar"
                width={128}
                height={128}
                className="w-full h-full object-cover rounded-full border-4 border-purple-600 shadow-lg"
              />
            </div>
          </div>
          
          {/* Loading text */}
          <div className="space-y-3">
            <h2 className="text-2xl font-bold text-gray-700">Loading Bidness Chat</h2>
            <p className="text-gray-600">Fetching your conversations...</p>
            
            {/* Animated dots */}
            <div className="flex justify-center space-x-1">
              <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style={{animationDelay: '0ms'}}></div>
              <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style={{animationDelay: '150ms'}}></div>
              <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style={{animationDelay: '300ms'}}></div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-200 via-purple-100 to-blue-200 flex relative">
      {/* Mobile Backdrop */}
      {isMobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar - Conversations List */}
      <div className={`w-80 bg-white border-r-4 border-gray-800 flex flex-col shadow-xl transition-transform duration-300 ease-in-out lg:static lg:translate-x-0 z-50 ${
        isMobileMenuOpen ? 'fixed inset-y-0 left-0 translate-x-0' : 'fixed inset-y-0 left-0 -translate-x-full lg:relative lg:translate-x-0'
      }`}>
        {/* Header */}
        <div className="p-3 lg:p-4 border-b-4 border-gray-800 bg-gradient-to-r from-blue-600 to-purple-600 text-white">
          <div className="flex justify-between items-center">
            <h1 className="text-lg lg:text-xl font-bold">💬 Bidness Chat</h1>
            <button
              onClick={handleLogout}
              className="text-xs lg:text-sm bg-white/20 hover:bg-white/30 backdrop-blur px-2 lg:px-3 py-1 rounded-full transition-all hover:cursor-pointer border border-white/40"
            >
              Logout
            </button>
          </div>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto max-h-[calc(100vh-120px)] lg:max-h-[calc(100vh-80px)]">
          {Object.keys(conversations).length === 0 ? (
            <div className="p-4 text-gray-500 text-center">
              <div className="text-4xl mb-2">📱</div>
              <div>No conversations found</div>
            </div>
          ) : Object.keys(conversations)
              .filter((contact) => {
                const messages = conversations[contact];
                // Show conversations that have at least one inbound message (they replied at least once)
                return messages.some(message => message.direction === 'inbound');
              }).length === 0 ? (
            <div className="p-4 text-gray-500 text-center">
              <div className="text-4xl mb-2">💬</div>
              <div>No active conversations</div>
              <div className="text-xs mt-2">Conversations will appear here when contacts reply</div>
            </div>
          ) : (
            Object.keys(conversations)
              .filter((contact) => {
                const messages = conversations[contact];
                // Show conversations that have at least one inbound message (they replied at least once)
                return messages.some((message: Message) => message.direction === 'inbound');
              })
              .sort((contactA, contactB) => {
                // Sort by most recent message timestamp (newest first)
                const lastMessageA = conversations[contactA][conversations[contactA].length - 1];
                const lastMessageB = conversations[contactB][conversations[contactB].length - 1];
                
                const timeA = new Date(lastMessageA.date_sent).getTime();
                const timeB = new Date(lastMessageB.date_sent).getTime();
                
                return timeB - timeA; // Newest first
              })
              .map((contact) => {
              const lastMessage = conversations[contact][conversations[contact].length - 1];
              const isUnread = isUnreadConversation(conversations[contact]);
              return (
                <div
                  key={contact}
                  onClick={() => handleContactSelect(contact)}
                  className={`p-3 lg:p-4 border-b-2 border-gray-700 cursor-pointer hover:bg-gradient-to-r hover:from-blue-50 hover:to-purple-50 transition-all ${
                    selectedContact === contact ? 'bg-gradient-to-r from-blue-100 to-purple-100 border-l-4 border-l-blue-500 shadow-sm' : ''
                  }`}
                >
                  <div className="flex items-center space-x-2 lg:space-x-3">
                    <div className="relative">
                      <div className="w-8 lg:w-10 h-8 lg:h-10 rounded-full overflow-hidden border-2 border-gray-600 shadow-sm">
                        <Image
                          src="/sonal.png"
                          alt="Contact Avatar"
                          width={40}
                          height={40}
                          className="w-full h-full object-cover"
                        />
                      </div>
                      {isUnread && (
                        <div className="absolute -top-1 -right-1 w-3 lg:w-4 h-3 lg:h-4 bg-red-500 rounded-full flex items-center justify-center border border-white">
                          <span className="text-white text-xs font-bold">!</span>
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-gray-800 text-sm lg:text-base truncate">
                        {formatPhoneNumber(contact)}
                      </div>
                      <div className="text-xs lg:text-sm text-gray-600 truncate">
                        {lastMessage?.body ? truncateMessage(lastMessage.body) : 'No messages'}
                      </div>
                      <div className="text-xs text-gray-400 mt-1">
                        {lastMessage?.date_sent ? formatTime(lastMessage.date_sent) : ''}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col w-full lg:w-auto">
        {/* Mobile Header */}
        <div className="lg:hidden p-4 bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg border-b-4 border-gray-800">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setIsMobileMenuOpen(true)}
              className="p-2 rounded-lg bg-white/20 hover:bg-white/30 transition-all"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <h1 className="text-lg font-bold">💬 Bidness Chat</h1>
            <button
              onClick={handleLogout}
              className="text-sm bg-white/20 hover:bg-white/30 backdrop-blur px-3 py-1 rounded-full transition-all border border-white/40"
            >
              Logout
            </button>
          </div>
        </div>

        {selectedContact ? (
          <>
            {/* Chat Header - Hidden on mobile */}
            <div className="hidden lg:block p-4 border-b-4 border-gray-800 bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 rounded-full overflow-hidden border-2 border-white">
                  <Image
                    src="/sonal.png"
                    alt="Contact Avatar"
                    width={32}
                    height={32}
                    className="w-full h-full object-cover"
                  />
                </div>
                <h2 className="text-lg font-bold">
                  {formatPhoneNumber(selectedContact)}
                </h2>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto bg-gradient-to-br from-slate-100 via-blue-50 to-purple-50 max-h-[calc(100vh-280px)] lg:max-h-[calc(100vh-200px)]">
              <div className="p-3 lg:p-6 space-y-4 lg:space-y-6">
                {conversations[selectedContact]?.map((message) => (
                  <div
                    key={message.sid}
                    className={`flex ${
                      message.direction === 'outbound' ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    <div
                      className={`max-w-[280px] sm:max-w-xs lg:max-w-md px-3 lg:px-4 py-2 lg:py-3 rounded-2xl shadow-lg border-2 ${
                        message.direction === 'outbound'
                          ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white border-blue-600'
                          : 'bg-gradient-to-r from-gray-100 to-white text-gray-800 border-gray-400'
                      }`}
                    >
                      <div className="text-sm font-medium break-words">{message.body}</div>
                      <div
                        className={`text-xs mt-2 ${
                          message.direction === 'outbound' ? 'text-blue-100' : 'text-gray-500'
                        }`}
                      >
                        {formatTime(message.date_sent)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Message Input */}
            <div className="p-3 lg:p-4 bg-gradient-to-r from-gray-50 to-white border-t-4 border-gray-800">
              {/* Quick Message Button */}
              <div className="mb-3 flex justify-center">
                <button
                  onClick={() => setNewMessage("I recently just finished an AI phone agent that turns incoming calls into booked appointments automatically. I'm looking to set up a few businesses for essentially free while I set up testimonials. Would you be open to hearing more? I can also send you a demo call with a phone agent.<br />I recently just finished an AI phone agent that turns incoming calls into booked appointments automatically. I'm looking to set up a few businesses for essentially free while I set up testimonials. Would you be open to hearing more? I can also send you a demo call with a phone agent.")}
                  className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition duration-200 border border-purple-600 shadow-sm hover:cursor-pointer"
                >
                  � Use Full Pitch
                </button>
              </div>
              
              <div className="flex space-x-2 lg:space-x-3">
                <input
                  type="text"
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && !sending && sendMessage()}
                  placeholder="Type a message..."
                  className="flex-1 px-3 lg:px-4 py-2 lg:py-3 border-2 border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500 text-black bg-white shadow-inner text-sm lg:text-base"
                  disabled={sending}
                />
                <button
                  onClick={sendMessage}
                  disabled={sending || !newMessage.trim()}
                  className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white px-4 lg:px-6 py-2 lg:py-3 rounded-xl transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed hover:cursor-pointer border-2 border-purple-600 shadow-lg font-bold text-sm lg:text-base"
                >
                  {sending ? 'Sending...' : 'Send'}
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center bg-gradient-to-br from-slate-100 via-blue-50 to-purple-50 p-4">
            <div className="text-center">
              <div className="text-4xl lg:text-6xl mb-4">💬</div>
              <div className="text-gray-500 text-lg lg:text-xl font-semibold">Select a conversation to start chatting</div>
              <div className="text-gray-400 text-sm mt-2">
                <span className="lg:hidden">Tap the menu button to see conversations</span>
                <span className="hidden lg:inline">Choose from your conversations on the left</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}