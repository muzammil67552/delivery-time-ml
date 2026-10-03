/**
 * Delivery Time Predictor — Phase 17 Frontend Controller
 * Handles form validation, asynchronous API communication, loading state,
 * and user-friendly error/result rendering.
 */

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("prediction-form");
  const submitBtn = document.getElementById("submit-btn");
  const resetBtn = document.getElementById("reset-btn");
  const spinner = document.getElementById("spinner");
  const btnText = submitBtn.querySelector(".btn-text");

  const resultCard = document.getElementById("result-card");
  const predictedMinutesSpan = document.getElementById("predicted-minutes");
  const errorCard = document.getElementById("error-card");
  const errorMessage = document.getElementById("error-message");
  const endpointLabel = document.getElementById("api-endpoint-label");

  // Determine API endpoint depending on origin
  function getApiEndpoint() {
    if (
      window.location.protocol.startsWith("http") &&
      window.location.origin &&
      window.location.origin !== "null"
    ) {
      return `${window.location.origin}/predict`;
    }
    // Default fallback if accessed as local file:// in browser
    return "http://127.0.0.1:8000/predict";
  }

  const API_ENDPOINT = getApiEndpoint();
  if (endpointLabel) {
    endpointLabel.textContent = API_ENDPOINT;
  }

  // Set loading state
  function setLoading(isLoading) {
    if (isLoading) {
      submitBtn.disabled = true;
      spinner.classList.remove("hidden");
      btnText.textContent = "Calculating...";
      resultCard.classList.add("hidden");
      errorCard.classList.add("hidden");
    } else {
      submitBtn.disabled = false;
      spinner.classList.add("hidden");
      btnText.textContent = "Predict Delivery Time";
    }
  }

  // Display prediction result
  function showResult(minutes) {
    predictedMinutesSpan.textContent = Number(minutes).toFixed(2);
    resultCard.classList.remove("hidden");
    errorCard.classList.add("hidden");
  }

  // Display error message
  function showError(msg) {
    errorMessage.textContent = msg;
    errorCard.classList.remove("hidden");
    resultCard.classList.add("hidden");
  }

  // Validate form inputs client-side
  function validateInputs(data) {
    if (isNaN(data.Distance_km) || data.Distance_km <= 0 || data.Distance_km > 100) {
      return "Distance must be a positive number up to 100 km.";
    }
    if (isNaN(data.Preparation_Time_min) || data.Preparation_Time_min < 0 || data.Preparation_Time_min > 180) {
      return "Kitchen Preparation Time must be between 0 and 180 minutes.";
    }
    if (isNaN(data.Courier_Experience_yrs) || data.Courier_Experience_yrs < 0 || data.Courier_Experience_yrs > 50) {
      return "Courier Experience must be between 0 and 50 years.";
    }
    if (!data.Weather || !data.Traffic_Level || !data.Time_of_Day || !data.Vehicle_Type) {
      return "Please select valid categorical options for all required fields.";
    }
    return null;
  }

  // Handle form submission
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    // Construct raw payload
    const payload = {
      Distance_km: parseFloat(document.getElementById("distance").value),
      Weather: document.getElementById("weather").value,
      Traffic_Level: document.getElementById("traffic").value,
      Time_of_Day: document.getElementById("time-of-day").value,
      Vehicle_Type: document.getElementById("vehicle").value,
      Preparation_Time_min: parseFloat(document.getElementById("prep-time").value),
      Courier_Experience_yrs: parseFloat(document.getElementById("experience").value),
    };

    // Client-side validation check
    const validationError = validateInputs(payload);
    if (validationError) {
      showError(validationError);
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(API_ENDPOINT, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        // Handle FastAPI validation error format (detail array or string)
        let message = "Prediction request failed.";
        if (typeof data.detail === "string") {
          message = data.detail;
        } else if (Array.isArray(data.detail)) {
          message = data.detail.map((err) => `${err.loc.join(" -> ")}: ${err.msg}`).join("; ");
        }
        showError(message);
      } else {
        showResult(data.predicted_delivery_time_min);
      }
    } catch (err) {
      showError(
        `Unable to reach the prediction API at ${API_ENDPOINT}. Ensure the FastAPI server is running with 'uvicorn app.main:app --reload'. Error: ${err.message}`
      );
    } finally {
      setLoading(false);
    }
  });

  // Reset to default sample values
  resetBtn.addEventListener("click", () => {
    document.getElementById("distance").value = "8.5";
    document.getElementById("weather").value = "Clear";
    document.getElementById("traffic").value = "Medium";
    document.getElementById("time-of-day").value = "Evening";
    document.getElementById("vehicle").value = "Scooter";
    document.getElementById("prep-time").value = "15";
    document.getElementById("experience").value = "3.0";

    resultCard.classList.add("hidden");
    errorCard.classList.add("hidden");
  });
});
