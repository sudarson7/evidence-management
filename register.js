document.addEventListener("DOMContentLoaded", () => {
    const registerForm = document.getElementById("registerForm");
    if (!registerForm) return;

    registerForm.addEventListener("submit", async function (e) {
        e.preventDefault();

        const fullname = document.getElementById("fullname").value.trim();
        const email = document.getElementById("email").value.trim();
        const phone = document.getElementById("phone").value.trim();
        const role = document.getElementById("role").value;
        const password = document.getElementById("password").value.trim();
        const msgEl = document.getElementById("message");

        if (!fullname || !email || !phone || !role || !password) {
            if (msgEl) {
                msgEl.style.color = "var(--danger)";
                msgEl.innerText = "Please complete all registration fields.";
            }
            showToast("Please fill all fields.", "error");
            return;
        }

        const userData = { fullname, email, phone, role, password };

        try {
            const response = await fetch("/register", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(userData)
            });

            const result = await response.json();

            if (msgEl) {
                msgEl.style.color = result.success ? "var(--success)" : "var(--danger)";
                msgEl.innerText = result.message;
            }

            if (result.success) {
                showToast(result.message, "success");
                setTimeout(() => {
                    window.location.href = "/login";
                }, 1000);
            } else {
                showToast(result.message, "error");
            }
        } catch (err) {
            console.error("Registration error:", err);
            if (msgEl) {
                msgEl.style.color = "var(--danger)";
                msgEl.innerText = "Failed to communicate with server.";
            }
            showToast("Server Error", "error");
        }
    });
});