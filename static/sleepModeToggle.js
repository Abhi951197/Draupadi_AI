// static/js/sleepModeToggle.js

class SleepModeToggle {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.isSleeping = false;
        this.remainingTime = 0;
        this.initialize();
    }

    async initialize() {
        this.render();
        await this.checkSleepStatus();
        setInterval(() => this.checkSleepStatus(), 1000);
    }

    async checkSleepStatus() {
        try {
            const response = await fetch('/sleep_status');
            const data = await response.json();
            this.isSleeping = data.sleeping;
            this.remainingTime = Math.ceil(data.remaining_minutes);
            this.updateUI();
        } catch (error) {
            console.error('Error checking sleep status:', error);
        }
    }

    async toggleSleep() {
        try {
            const response = await fetch('/toggle_sleep', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ sleeping: !this.isSleeping }),
            });
            
            const data = await response.json();
            this.isSleeping = data.sleeping;
            this.updateUI();
        } catch (error) {
            console.error('Error toggling sleep mode:', error);
        }
    }

    render() {
        this.container.innerHTML = `
        <div class="relative">
            <button id="sleepToggleBtn" class="flex items-center gap-2 px-2 py-2 rounded-full transition-all duration-300">
                <span class="icon"></span>
                <span class="text">Sleep OFF</span>
            </button>
            <div id="sleepTimer" class="hidden text-sm text-gray-600"></div>
        </div>
    `;

        this.toggleBtn = document.getElementById('sleepToggleBtn');
        this.timerDiv = document.getElementById('sleepTimer');
        this.toggleBtn.addEventListener('click', () => this.toggleSleep());
    }

    updateUI() {
        // Update button appearance
        this.toggleBtn.className = `flex items-center gap-2 px-4 py-2 rounded-full transition-all duration-300 ${
            this.isSleeping
                ? 'bg-purple-600 text-white hover:bg-purple-700' // Changed to purple to match theme
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'  // Light gray when inactive
        }`;

        // Update icon and text
        const iconSpan = this.toggleBtn.querySelector('.icon');
        const textSpan = this.toggleBtn.querySelector('.text');
        
        if (this.isSleeping) {
            iconSpan.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>`;
            textSpan.textContent = 'Sleep ON';
            this.timerDiv.textContent = `Resume in: ${this.remainingTime} min`;
            this.timerDiv.classList.remove('hidden');
            this.timerDiv.className = 'text-sm text-white'; // Changed to white text

        } else {
            iconSpan.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>`;
            textSpan.textContent = 'Sleep OFF';
            this.timerDiv.classList.add('hidden');
        }
    }
}