function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) { // Failsafe if container isn't on the page
        console.warn('Toast container not found. Falling back to alert for message:', message);
        alert(message); // Fallback for critical alerts if container is missing
        return;
    }

    const toast = document.createElement('div');
    toast.className = `toast-message ${type}`; // e.g., 'toast-message success'
    toast.textContent = message;

    container.appendChild(toast);

    // Trigger the slide-in animation
    setTimeout(() => {
        toast.classList.add('show');
    }, 10); // Small delay to allow CSS to apply initial state

    // Remove the toast after duration
    setTimeout(() => {
        toast.classList.remove('show');
        // Remove from DOM after transition
        toast.addEventListener('transitionend', () => {
            if (toast.parentElement) { // Check if it hasn't been removed by other means
               toast.remove();
            }
        }, { once: true });
    }, duration);
}
