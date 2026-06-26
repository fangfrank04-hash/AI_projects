import re

with open('App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace handleSend function
old_pattern = r'  const handleSend = async \(\) => \{.*?    setIsTyping\(false\);\n  \};'
new_handle = '''  const handleSend = async () => {
    if (!inputValue.trim() || isTyping) return;
    const userText = inputValue;

    streamingMsgIdRef.current = null;
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', text: userText }]);
    setInputValue('');
    setIsTyping(true);

    if (!isCurrentUserPM) {
       setMessages(prev => [...prev, { id: Date.now()+1, role: 'ai', text: `❌ 权限拒绝：抱歉 ${currentUser}，您非项目经理，无权进行编辑。` }]);
       setIsTyping(false);
       return;
    }

    await sseClient.sendMessage(userText);
  };'''

content = re.sub(old_pattern, new_handle, content, flags=re.DOTALL)

with open('App.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
