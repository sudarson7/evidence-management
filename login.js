document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById("loginForm");
    if (!loginForm) return;

    loginForm.addEventListener("submit", async function (e) {
        e.preventDefault();

        const email = document.getElementById("email").value.trim();
        const password = document.getElementById("password").value.trim();
        const role = document.getElementById("role").value;
        const msgEl = document.getElementById("message");
        const submitBtn = document.getElementById("loginBtn");

        if (!email || !password || !role) {
            if (msgEl) msgEl.innerText = "Please fill in all credentials and select a role.";
            showToast("Please fill in all fields.", "error");
            return;
        }

        try {
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerText = "Authenticating...";
            }

            const response = await fetch("/login", {
                credentials: "same-origin",
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    email: email,
                    password: password,
                    role: role
                })
            });

            const result = await response.json();

            if (result.success) {
                showToast(result.message, "success");
                if (result.otp) {
                    window.location.href = "/verify_otp";
                } else {
                    window.location.href = "/dashboard";
                }
            } else {
                if (msgEl) msgEl.innerText = result.message;
                showToast(result.message, "error");
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerText = "🔓 Authenticate & Request OTP";
                }
            }
        } catch (error) {
            console.error("Login Error:", error);
            if (msgEl) msgEl.innerText = "Server communication failure.";
            showToast("Server communication error.", "error");
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerText = "🔓 Authenticate & Request OTP";
            }
        }
    });
});