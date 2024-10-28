document.getElementById('chat-form').addEventListener('submit', function(event) {
    event.preventDefault();
    const inputText = document.getElementById('user-input').value;

    fetch('/generate_response', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ input_text: inputText })
    })
    .then(response => response.json())
    .then(data => {
        const chatHistory = document.getElementById('chat-history');
        chatHistory.innerHTML += `<div><strong>🧑 User:</strong> ${inputText}</div>`;
        chatHistory.innerHTML += `<div><strong>🧠 Assistant:</strong> ${data.response}</div>`;
        chatHistory.innerHTML += `<hr>`;
        document.getElementById('user-input').value = '';
    });
});
