/**
 * Delivery Time Predictor & Merchant Intelligence Controller
 * Controls:
 * 1. Hotel Profile & SQLite Persistence (Onboarding modal, city hubs, GPS coordinates)
 * 2. Interactive Live Map & Courier GPS Route Tracker (Leaflet.js + OpenStreetMap - Option 1)
 * 3. Real Street Address Geocoding & Route Distance Calculator (Option 3)
 * 4. Tab Navigation (Single Prediction, Batch Excel, Model Retraining, Order History)
 * 5. Real-Time Single Order Prediction with Live Courier Route Animation
 * 6. Batch Excel/CSV File Prediction & KPI Dashboard
 * 7. Automated Hotel Model Retraining & Evaluation Report
 * 8. SQLite Order History Table & CSV Export
 */

document.addEventListener("DOMContentLoaded", () => {
  const API_BASE = (
    window.location.protocol.startsWith("http") &&
    window.location.origin &&
    window.location.origin !== "null"
  ) ? window.location.origin : "http://127.0.0.1:8000";

  // =========================================================================
  // State & Coordinates
  // =========================================================================
  let hotelState = {
    name: "The Grand Hotel & Suites",
    address: "Union Square Grand Hotel, East 14th St, New York",
    lat: 40.7306,
    lng: -73.9866,
    city_preset: "New York",
    prep_time: 15,
    vehicle: "Scooter",
  };

  let currentDestLat = 40.7484;
  let currentDestLng = -73.9857;
  let currentRouteCoords = [];
  let cityPresetsData = {};
  let isAnimatingCourier = false;

  // =========================================================================
  // 1. Hotel Profile & SQLite Onboarding Modal
  // =========================================================================
  const hotelModal = document.getElementById("hotel-modal");
  const openSettingsBtn = document.getElementById("open-settings-btn");
  const closeModalBtn = document.getElementById("close-modal-btn");
  const cancelModalBtn = document.getElementById("cancel-modal-btn");
  const hotelProfileForm = document.getElementById("hotel-profile-form");

  const hotelHeaderName = document.getElementById("hotel-header-name");
  const hotelHeaderSub = document.getElementById("hotel-header-sub");
  const modalHotelName = document.getElementById("modal-hotel-name");
  const modalCityPreset = document.getElementById("modal-city-preset");
  const modalHotelAddress = document.getElementById("modal-hotel-address");
  const modalHotelLat = document.getElementById("modal-hotel-lat");
  const modalHotelLng = document.getElementById("modal-hotel-lng");
  const modalPrepTime = document.getElementById("modal-prep-time");
  const modalVehicle = document.getElementById("modal-vehicle");
  const modalEmail = document.getElementById("modal-email");
  const modalPhone = document.getElementById("modal-phone");

  const hotelOriginDisplay = document.getElementById("hotel-origin-display");
  const prepTimeInput = document.getElementById("prep-time");
  const vehicleSelect = document.getElementById("vehicle");
  const distanceInput = document.getElementById("distance");
  const destinationAddressInput = document.getElementById("destination-address-input");
  const landmarkPillsContainer = document.getElementById("landmark-pills-container");
  const navbarHotelName = document.getElementById("navbar-hotel-name");
  const navbarModelBadge = document.getElementById("navbar-model-badge");

  function openHotelModal() {
    if (hotelModal) hotelModal.classList.remove("hidden");
  }

  function closeHotelModal() {
    if (hotelModal) hotelModal.classList.add("hidden");
  }

  if (openSettingsBtn) openSettingsBtn.addEventListener("click", openHotelModal);
  if (closeModalBtn) closeModalBtn.addEventListener("click", closeHotelModal);
  if (cancelModalBtn) cancelModalBtn.addEventListener("click", closeHotelModal);

  // Fetch supported city presets from backend
  async function loadCityPresets() {
    try {
      const res = await fetch(`${API_BASE}/api/city-presets`);
      if (res.ok) {
        const data = await res.json();
        cityPresetsData = data.presets || {};
      }
    } catch (e) {
      console.warn("Could not load city presets:", e);
    }
  }

  // Update modal lat/lng when city preset changes
  if (modalCityPreset) {
    modalCityPreset.addEventListener("change", () => {
      const chosen = modalCityPreset.value;
      if (cityPresetsData[chosen]) {
        const preset = cityPresetsData[chosen];
        if (modalHotelAddress) modalHotelAddress.value = preset.hotel_address;
        if (modalHotelLat) modalHotelLat.value = preset.default_lat;
        if (modalHotelLng) modalHotelLng.value = preset.default_lng;
      }
    });
  }

  // Load existing hotel profile on startup (silently with sensible defaults)
  async function loadHotelProfile() {
    await loadCityPresets();
    try {
      const res = await fetch(`${API_BASE}/api/hotel-profile`);
      if (!res.ok) {
        initMap();
        renderLandmarkPills();
        return;
      }
      const data = await res.json();

      if (data.is_configured && data.profile) {
        const p = data.profile;
        hotelState.name = p.hotel_name || "Hotel Express Hub";
        hotelState.address = p.branch_or_address || "Operational Hub";
        hotelState.lat = parseFloat(p.latitude) || 40.7306;
        hotelState.lng = parseFloat(p.longitude) || -73.9866;
        hotelState.city_preset = p.city_preset || "New York";
        hotelState.prep_time = p.default_prep_time_min || 15;
        hotelState.vehicle = p.default_vehicle_type || "Scooter";

        if (hotelHeaderName) hotelHeaderName.textContent = p.hotel_name;
        if (hotelHeaderSub) hotelHeaderSub.textContent = p.branch_or_address || `${hotelState.city_preset} Hub`;
        if (hotelOriginDisplay) {
          hotelOriginDisplay.value = p.branch_or_address 
            ? `${p.hotel_name} (${p.branch_or_address})` 
            : `${p.hotel_name} (${hotelState.city_preset})`;
        }

        // Update Navbar Hotel Chip with Hotel Name and Street Address
        if (navbarHotelName) {
          navbarHotelName.textContent = p.branch_or_address 
            ? `${p.hotel_name} • ${p.branch_or_address}` 
            : (p.city_preset ? `${p.hotel_name} • ${p.city_preset}` : p.hotel_name);
          navbarHotelName.title = `${p.hotel_name} - ${p.branch_or_address || ''} (${p.city_preset || ''})`;
        }
        if (navbarModelBadge) {
          if (p.has_custom_model) {
            navbarModelBadge.innerHTML = "&#11088; Custom Model";
            navbarModelBadge.style.background = "#ecfdf5";
            navbarModelBadge.style.color = "#047857";
            navbarModelBadge.style.borderColor = "#a7f3d0";
          } else {
            navbarModelBadge.innerHTML = "&#9889; Production Model";
            navbarModelBadge.style.background = "#eef2ff";
            navbarModelBadge.style.color = "#4338ca";
            navbarModelBadge.style.borderColor = "#c7d2fe";
          }
        }

        // Pre-fill prediction defaults
        if (prepTimeInput) prepTimeInput.value = p.default_prep_time_min || 15;
        if (vehicleSelect) vehicleSelect.value = p.default_vehicle_type || "Scooter";

        // Setup map with configured hotel coordinates and street address
        initMap();
        if (map && hotelMarker) {
          hotelMarker.setLatLng([hotelState.lat, hotelState.lng]);
          hotelMarker.bindPopup(`<b>🏨 ${hotelState.name}</b><br><small>${hotelState.address || "Dispatch Origin"}</small><br><span style="color:#6366f1;font-size:0.75rem;">${hotelState.city_preset}</span>`).openPopup();
          
          currentDestLat = hotelState.lat + 0.018;
          currentDestLng = hotelState.lng + 0.012;
          if (destMarker) {
            destMarker.setLatLng([currentDestLat, currentDestLng]);
          }
          map.setView([hotelState.lat, hotelState.lng], 13);
          calculateAndDrawRoute(
            currentDestLat, 
            currentDestLng, 
            destinationAddressInput && destinationAddressInput.value ? destinationAddressInput.value : `Customer Destination (${hotelState.city_preset})`
          );
        }
        renderLandmarkPills();
      } else {
        // If hotel profile is not yet configured and not in guest/preview mode, guide visitor to /welcome
        const isGuest = window.location.search.includes("guest=1") || window.location.search.includes("preview=1");
        if (!isGuest) {
          window.location.href = "/welcome";
          return;
        }
        initMap();
        renderLandmarkPills();
      }
    } catch (err) {
      console.warn("Could not load hotel profile from SQLite:", err);
      initMap();
      renderLandmarkPills();
    }
  }

  if (hotelProfileForm) {
    hotelProfileForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        hotel_name: modalHotelName ? modalHotelName.value.trim() : "Hotel Hub",
        branch_or_address: modalHotelAddress ? modalHotelAddress.value.trim() : "",
        default_prep_time_min: modalPrepTime ? (parseFloat(modalPrepTime.value) || 15.0) : 15.0,
        default_vehicle_type: modalVehicle ? modalVehicle.value : "Scooter",
        latitude: modalHotelLat ? (parseFloat(modalHotelLat.value) || 40.7306) : 40.7306,
        longitude: modalHotelLng ? (parseFloat(modalHotelLng.value) || -73.9866) : -73.9866,
        city_preset: modalCityPreset ? modalCityPreset.value : "New York",
        contact_email: modalEmail ? modalEmail.value.trim() : "",
        contact_phone: modalPhone ? modalPhone.value.trim() : "",
      };

      try {
        const res = await fetch(`${API_BASE}/api/hotel-profile`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (res.ok) {
          const data = await res.json();
          const p = data.profile;
          hotelState.name = p.hotel_name;
          hotelState.address = p.branch_or_address;
          hotelState.lat = parseFloat(p.latitude) || 40.7306;
          hotelState.lng = parseFloat(p.longitude) || -73.9866;
          hotelState.city_preset = p.city_preset || "New York";

          if (hotelHeaderName) hotelHeaderName.textContent = p.hotel_name;
          if (hotelHeaderSub) hotelHeaderSub.textContent = p.branch_or_address || `${hotelState.city_preset} Hub`;
          if (hotelOriginDisplay) {
            hotelOriginDisplay.value = `${p.hotel_name} (${hotelState.city_preset})`;
          }
          if (prepTimeInput) prepTimeInput.value = p.default_prep_time_min;
          if (vehicleSelect) vehicleSelect.value = p.default_vehicle_type;

          // Reposition hotel marker and refresh landmarks
          updateHotelMapPosition();
          renderLandmarkPills();
          closeHotelModal();
        } else {
          alert("Failed to save hotel profile. Please check inputs.");
        }
      } catch (err) {
        alert(`Error saving hotel profile: ${err.message}`);
      }
    });
  }

  // =========================================================================
  // 2. Interactive Leaflet Map & Courier GPS Tracker (Option 1 & 3)
  // =========================================================================
  let map = null;
  let hotelMarker = null;
  let destMarker = null;
  let routePolyline = null;
  let courierMarker = null;

  const mapStatusText = document.getElementById("map-status-text");
  const mapDistanceBadge = document.getElementById("map-distance-badge");
  const mapEstDrive = document.getElementById("map-est-drive");
  const replayCourierBtn = document.getElementById("replay-courier-btn");
  const routeSourceBadge = document.getElementById("route-source-badge");

  function getVehicleEmoji(type) {
    if (type === "Bike") return "🚲";
    if (type === "Car") return "🚗";
    return "🛵";
  }

  function initMap() {
    if (map !== null) return;
    const mapElement = document.getElementById("delivery-map");
    if (!mapElement || typeof L === "undefined") return;

    // Default destination slightly offset from hotel
    currentDestLat = hotelState.lat + 0.018;
    currentDestLng = hotelState.lng + 0.012;

    map = L.map("delivery-map", {
      center: [hotelState.lat, hotelState.lng],
      zoom: 13,
      zoomControl: true,
      attributionControl: false,
    });

    // 100% Free Public OpenStreetMap Tiles (Zero API key required!)
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors',
    }).addTo(map);

    // Invalidate map size so container renders completely
    setTimeout(() => {
      if (map) map.invalidateSize();
    }, 250);

    // Hotel Origin Icon
    const hotelIcon = L.divIcon({
      className: "custom-marker-wrapper",
      html: '<div class="hotel-marker-pin" title="Hotel Hub Origin">🏨</div>',
      iconSize: [34, 34],
      iconAnchor: [17, 17],
    });

    hotelMarker = L.marker([hotelState.lat, hotelState.lng], { icon: hotelIcon })
      .addTo(map)
      .bindPopup(`<b>🏨 ${hotelState.name}</b><br><small>${hotelState.address || "Dispatch Origin"}</small>`);

    // Customer Destination Icon (Draggable)
    const destIcon = L.divIcon({
      className: "custom-marker-wrapper",
      html: '<div class="customer-marker-pin" title="Drag to adjust drop-off point">📍</div>',
      iconSize: [32, 32],
      iconAnchor: [16, 32],
    });

    destMarker = L.marker([currentDestLat, currentDestLng], {
      icon: destIcon,
      draggable: true,
    })
      .addTo(map)
      .bindPopup("<b>📍 Customer Destination</b><br><small>Drag or click map to change</small>");

    destMarker.on("dragend", (e) => {
      const pos = e.target.getLatLng();
      calculateAndDrawRoute(pos.lat, pos.lng, `Dropoff Point (${pos.lat.toFixed(4)}, ${pos.lng.toFixed(4)})`);
    });

    // Courier Marker (Moving tracker)
    const courierIcon = L.divIcon({
      className: "custom-marker-wrapper",
      html: `<div class="courier-marker-pin" id="courier-icon-el">${getVehicleEmoji(vehicleSelect ? vehicleSelect.value : "Scooter")}</div>`,
      iconSize: [38, 38],
      iconAnchor: [19, 19],
    });

    courierMarker = L.marker([hotelState.lat, hotelState.lng], {
      icon: courierIcon,
      zIndexOffset: 1000,
      opacity: 0,
    }).addTo(map);

    // Click anywhere on map to reposition customer dropoff
    map.on("click", (e) => {
      calculateAndDrawRoute(e.latlng.lat, e.latlng.lng, `Location (${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)})`);
    });

    // Initial route calculation
    calculateAndDrawRoute(currentDestLat, currentDestLng, destinationAddressInput ? destinationAddressInput.value : "Commercial District");
  }

  function updateHotelMapPosition() {
    if (!map || !hotelMarker) return;
    hotelMarker.setLatLng([hotelState.lat, hotelState.lng]);
    hotelMarker.setPopupContent(`<b>🏨 ${hotelState.name}</b><br><small>${hotelState.address}</small><br><span style="color:#6366f1;font-size:0.75rem;">${hotelState.city_preset}</span>`);
    
    currentDestLat = hotelState.lat + 0.018;
    currentDestLng = hotelState.lng + 0.012;
    if (destMarker) {
      destMarker.setLatLng([currentDestLat, currentDestLng]);
    }
    map.setView([hotelState.lat, hotelState.lng], 13);
    calculateAndDrawRoute(currentDestLat, currentDestLng, destinationAddressInput && destinationAddressInput.value ? destinationAddressInput.value : `Customer Destination (${hotelState.city_preset})`);
  }

  // Update courier emoji when vehicle changes
  if (vehicleSelect) {
    vehicleSelect.addEventListener("change", () => {
      const el = document.getElementById("courier-icon-el");
      if (el) el.textContent = getVehicleEmoji(vehicleSelect.value);
    });
  }

  // Update route polyline, distance in form, and map view
  async function calculateAndDrawRoute(destLat, destLng, addressLabel = null) {
    currentDestLat = destLat;
    currentDestLng = destLng;

    if (destMarker) {
      destMarker.setLatLng([destLat, destLng]);
    }

    if (addressLabel && destinationAddressInput) {
      destinationAddressInput.value = addressLabel;
    }

    if (mapStatusText) {
      mapStatusText.textContent = `Routing to: ${addressLabel || "Dropoff Point"}`;
    }

    try {
      const url = `${API_BASE}/api/calculate-route?origin_lat=${hotelState.lat}&origin_lng=${hotelState.lng}&dest_lat=${destLat}&dest_lng=${destLng}`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();

      currentRouteCoords = data.route_coords || [];

      // Update distance input in prediction form
      if (distanceInput) {
        distanceInput.value = data.distance_km;
      }

      // Update badges
      if (mapDistanceBadge) mapDistanceBadge.textContent = `${data.distance_km} km`;
      if (mapEstDrive) mapEstDrive.textContent = `~${Math.round(data.duration_min)} min drive`;
      if (routeSourceBadge) {
        routeSourceBadge.textContent = data.source === "osrm_live" ? "OSRM Live Routing" : "Simulated Road Network";
      }

      // Draw route polyline
      if (routePolyline) {
        map.removeLayer(routePolyline);
      }

      routePolyline = L.polyline(currentRouteCoords, {
        color: "#4f46e5",
        weight: 5,
        opacity: 0.85,
        dashArray: "8, 6",
        lineCap: "round",
      }).addTo(map);

      // Fit map viewport to show both origin and destination
      if (currentRouteCoords.length > 0) {
        map.fitBounds(L.latLngBounds(currentRouteCoords), { padding: [35, 35] });
      }
    } catch (e) {
      console.warn("Route navigation calculation error:", e);
    }
  }

  // When user manually changes the Distance (km) input
  if (distanceInput) {
    distanceInput.addEventListener("change", () => {
      const km = parseFloat(distanceInput.value);
      if (isNaN(km) || km <= 0) return;

      // Move destination marker along bearing to roughly match typed distance
      const bearing = 0.65; // ~37 degrees northeast
      const latOffset = (km / 111.0) * Math.cos(bearing);
      const lngOffset = (km / (111.0 * Math.cos(hotelState.lat * Math.PI / 180))) * Math.sin(bearing);

      calculateAndDrawRoute(
        hotelState.lat + latOffset,
        hotelState.lng + lngOffset,
        `Dropoff Point (${km} km)`
      );
    });
  }

  // Render quick landmark buttons based on current city preset or local radius
  function renderLandmarkPills() {
    if (!landmarkPillsContainer) return;
    landmarkPillsContainer.innerHTML = '<span class="pills-label">Quick Dropoffs:</span>';

    let landmarks = [];
    const cityData = cityPresetsData[hotelState.city_preset];
    if (cityData && cityData.landmarks && cityData.landmarks.length > 0) {
      landmarks = cityData.landmarks;
    } else {
      const hLat = hotelState.lat;
      const hLng = hotelState.lng;
      landmarks = [
        { name: "Commercial District Hub", address: `Market Center (${(hLat + 0.012).toFixed(4)}, ${(hLng + 0.015).toFixed(4)})`, lat: hLat + 0.012, lng: hLng + 0.015 },
        { name: "North Residential", address: `Sector North (${(hLat + 0.022).toFixed(4)}, ${(hLng + 0.006).toFixed(4)})`, lat: hLat + 0.022, lng: hLng + 0.006 },
        { name: "East Boulevard", address: `East Corridor (${(hLat + 0.008).toFixed(4)}, ${(hLng + 0.025).toFixed(4)})`, lat: hLat + 0.008, lng: hLng + 0.025 },
        { name: "Business Quarter", address: `Commercial Center (${(hLat - 0.015).toFixed(4)}, ${(hLng - 0.018).toFixed(4)})`, lat: hLat - 0.015, lng: hLng - 0.018 },
      ];
    }

    landmarks.forEach((lm) => {
      const pill = document.createElement("button");
      pill.type = "button";
      pill.className = "landmark-pill";
      pill.textContent = lm.name;

      pill.addEventListener("click", () => {
        document.querySelectorAll(".landmark-pill").forEach((p) => p.classList.remove("active"));
        pill.classList.add("active");
        calculateAndDrawRoute(lm.lat, lm.lng, `${lm.name}, ${lm.address}`);
      });

      landmarkPillsContainer.appendChild(pill);
    });
  }

  // Live Courier Animation along route polyline
  function animateCourierRoute(coords, predictedEta) {
    if (!courierMarker || !coords || coords.length < 2) return;
    if (isAnimatingCourier) return;

    isAnimatingCourier = true;
    courierMarker.setOpacity(1);
    if (replayCourierBtn) replayCourierBtn.classList.remove("hidden");

    if (mapStatusText) {
      mapStatusText.textContent = `En Route 🛵 • Predicted ETA: ${predictedEta} min`;
    }

    let step = 0;
    const totalSteps = coords.length;
    const durationMs = 3500;
    const intervalMs = Math.max(25, durationMs / totalSteps);

    const animTimer = setInterval(() => {
      if (step < totalSteps) {
        courierMarker.setLatLng(coords[step]);
        step++;
      } else {
        clearInterval(animTimer);
        isAnimatingCourier = false;
        if (mapStatusText) {
          mapStatusText.textContent = `Order Dispatched! Arriving in ~${predictedEta} min`;
        }
      }
    }, intervalMs);
  }

  if (replayCourierBtn) {
    replayCourierBtn.addEventListener("click", () => {
      const eta = predictedMinutesSpan ? predictedMinutesSpan.textContent : "25";
      animateCourierRoute(currentRouteCoords, eta);
    });
  }

  // =========================================================================
  // Expandable Map Modal Controller
  // =========================================================================
  const mapContainerBox = document.getElementById("map-container-box");
  const expandMapBtn = document.getElementById("expand-map-btn");
  const closeExpandedBtn = document.getElementById("close-expanded-btn");
  const expandBtnText = document.getElementById("expand-btn-text");
  const topNavbar = document.querySelector(".top-navbar");

  function toggleMapExpansion() {
    if (!mapContainerBox) return;
    const isExpanded = mapContainerBox.classList.toggle("expanded-modal");
    document.body.classList.toggle("map-expanded-view", isExpanded);

    // Hide top navbar when map is expanded, restore when un-expanded
    if (topNavbar) {
      topNavbar.style.display = isExpanded ? "none" : "";
    }

    if (expandBtnText) {
      expandBtnText.textContent = isExpanded ? "Collapse Map" : "Expand Map";
    }
    if (isExpanded) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    setTimeout(() => {
      if (map) {
        map.invalidateSize();
        if (currentRouteCoords && currentRouteCoords.length > 0) {
          const paddingVal = isExpanded ? [55, 55] : [25, 25];
          map.fitBounds(L.latLngBounds(currentRouteCoords), { padding: paddingVal, maxZoom: 16 });
        } else if (hotelState && hotelState.lat) {
          map.setView([hotelState.lat, hotelState.lng], 13);
        }
      }
    }, 240);
  }

  if (expandMapBtn) expandMapBtn.addEventListener("click", toggleMapExpansion);
  if (closeExpandedBtn) closeExpandedBtn.addEventListener("click", toggleMapExpansion);

  // Close square modal on Escape key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && mapContainerBox && mapContainerBox.classList.contains("expanded-modal")) {
      toggleMapExpansion();
    }
  });

  // Close square modal when clicking outside on the backdrop
  document.addEventListener("mousedown", (e) => {
    if (mapContainerBox && mapContainerBox.classList.contains("expanded-modal")) {
      if (!mapContainerBox.contains(e.target) && (!expandMapBtn || !expandMapBtn.contains(e.target))) {
        toggleMapExpansion();
      }
    }
  });

  // =========================================================================
  // 3. Tab Navigation Logic
  // =========================================================================
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabButtons.forEach((b) => b.classList.remove("active"));
      tabContents.forEach((c) => c.classList.add("hidden"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      const targetTab = document.getElementById(targetId);
      if (targetTab) {
        targetTab.classList.remove("hidden");
      }

      if (targetId === "history-tab") {
        loadOrderHistory();
      }

      if (targetId === "riders-tab") {
        loadRidersList();
        loadFleetStats();
      }


      // Re-invalidate Leaflet map size on tab switch
      if (targetId === "single-tab" && map) {
        setTimeout(() => map.invalidateSize(), 150);
      }
    });
  });

  // =========================================================================
  // 4. Tab 1: Single Prediction Controller
  // =========================================================================
  const singleForm = document.getElementById("prediction-form");
  const singleSubmitBtn = document.getElementById("submit-btn");
  const singleResetBtn = document.getElementById("reset-btn");
  const singleSpinner = document.getElementById("spinner");
  const singleBtnText = singleSubmitBtn.querySelector(".btn-text");

  const idleCard = document.getElementById("idle-card");
  const resultCard = document.getElementById("result-card");
  const predictedMinutesSpan = document.getElementById("predicted-minutes");
  const errorCard = document.getElementById("error-card");
  const errorMessage = document.getElementById("error-message");

  function setSingleLoading(isLoading) {
    if (isLoading) {
      singleSubmitBtn.disabled = true;
      singleSpinner.classList.remove("hidden");
      singleBtnText.textContent = "Calculating ETA...";
      if (idleCard) idleCard.classList.add("hidden");
      resultCard.classList.add("hidden");
      errorCard.classList.add("hidden");
    } else {
      singleSubmitBtn.disabled = false;
      singleSpinner.classList.add("hidden");
      singleBtnText.textContent = "Predict Delivery Time";
    }
  }

  function showSingleResult(minutes) {
    predictedMinutesSpan.textContent = Number(minutes).toFixed(2);
    if (idleCard) idleCard.classList.add("hidden");
    resultCard.classList.remove("hidden");
    errorCard.classList.add("hidden");
  }

  function showSingleError(msg) {
    errorMessage.textContent = msg;
    if (idleCard) idleCard.classList.add("hidden");
    errorCard.classList.remove("hidden");
    resultCard.classList.add("hidden");
  }

  function validateSingleInputs(data) {
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
      return "Please select valid options for all required categorical fields.";
    }
    return null;
  }

  singleForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      Distance_km: parseFloat(document.getElementById("distance").value),
      Weather: document.getElementById("weather").value,
      Traffic_Level: document.getElementById("traffic").value,
      Time_of_Day: document.getElementById("time-of-day").value,
      Vehicle_Type: document.getElementById("vehicle").value,
      Preparation_Time_min: parseFloat(document.getElementById("prep-time").value),
      Courier_Experience_yrs: parseFloat(document.getElementById("experience").value),
      Destination_Address: destinationAddressInput ? destinationAddressInput.value : "",
      Dropoff_Lat: currentDestLat,
      Dropoff_Lng: currentDestLng,
    };

    const valErr = validateSingleInputs(payload);
    if (valErr) {
      showSingleError(valErr);
      return;
    }

    setSingleLoading(true);

    try {
      const response = await fetch(`${API_BASE}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        let msg = "Prediction request failed.";
        if (typeof data.detail === "string") {
          msg = data.detail;
        } else if (Array.isArray(data.detail)) {
          msg = data.detail.map((err) => `${err.loc.join(" -> ")}: ${err.msg}`).join("; ");
        }
        showSingleError(msg);
      } else {
        showSingleResult(data.predicted_delivery_time_min);
        // Animate courier along map route
        animateCourierRoute(currentRouteCoords, data.predicted_delivery_time_min);
        // Refresh history counter in background
        loadOrderHistory(true);
      }
    } catch (err) {
      showSingleError(`API Connection error: ${err.message}`);
    } finally {
      setSingleLoading(false);
    }
  });

  singleResetBtn.addEventListener("click", () => {
    document.getElementById("distance").value = "8.5";
    document.getElementById("weather").value = "Clear";
    document.getElementById("traffic").value = "Medium";
    document.getElementById("time-of-day").value = "Evening";
    document.getElementById("vehicle").value = modalVehicle ? modalVehicle.value : "Scooter";
    document.getElementById("prep-time").value = modalPrepTime ? modalPrepTime.value : "15";
    document.getElementById("experience").value = "3.0";

    resultCard.classList.add("hidden");
    errorCard.classList.add("hidden");
    if (idleCard) idleCard.classList.remove("hidden");
    if (courierMarker) courierMarker.setOpacity(0);
    if (replayCourierBtn) replayCourierBtn.classList.add("hidden");
  });

  // =========================================================================
  // 5. Tab 2: Batch Excel / CSV Prediction Controller
  // =========================================================================
  const batchForm = document.getElementById("batch-form");
  const batchFileInput = document.getElementById("batch-file-input");
  const batchFilenameDisplay = document.getElementById("batch-filename-display");
  const batchSubmitBtn = document.getElementById("batch-submit-btn");
  const batchSpinner = document.getElementById("batch-spinner");
  const batchBtnText = batchSubmitBtn.querySelector(".btn-text");
  const useCustomModelBatch = document.getElementById("use-custom-model-batch");

  const batchResultsSection = document.getElementById("batch-results-section");
  const batchErrorCard = document.getElementById("batch-error-card");
  const batchErrorMessage = document.getElementById("batch-error-message");
  const batchDownloadBtn = document.getElementById("batch-download-btn");

  const kpiTotal = document.getElementById("kpi-total");
  const kpiAvg = document.getElementById("kpi-avg");
  const kpiRange = document.getElementById("kpi-range");
  const kpiRisk = document.getElementById("kpi-risk");
  const batchTableBody = document.getElementById("batch-table-body");

  batchFileInput.addEventListener("change", () => {
    if (batchFileInput.files.length > 0) {
      const file = batchFileInput.files[0];
      batchFilenameDisplay.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
      batchFilenameDisplay.classList.remove("hidden");
      batchSubmitBtn.disabled = false;
    } else {
      batchFilenameDisplay.classList.add("hidden");
      batchSubmitBtn.disabled = true;
    }
  });

  function setBatchLoading(isLoading) {
    if (isLoading) {
      batchSubmitBtn.disabled = true;
      batchSpinner.classList.remove("hidden");
      batchBtnText.textContent = "Processing orders with ML pipeline...";
      batchErrorCard.classList.add("hidden");
      batchResultsSection.classList.add("hidden");
    } else {
      batchSubmitBtn.disabled = false;
      batchSpinner.classList.add("hidden");
      batchBtnText.textContent = "Process & Predict Batch";
    }
  }

  batchForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!batchFileInput.files.length) return;

    setBatchLoading(true);

    const formData = new FormData();
    formData.append("file", batchFileInput.files[0]);
    formData.append("use_custom_model", useCustomModelBatch.checked);

    try {
      const response = await fetch(`${API_BASE}/api/batch-predict`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        batchErrorMessage.textContent = data.detail || "Batch prediction failed.";
        batchErrorCard.classList.remove("hidden");
      } else {
        kpiTotal.textContent = data.total_orders;
        kpiAvg.textContent = `${data.avg_delivery_time_min} min`;
        kpiRange.textContent = `${data.min_delivery_time_min} - ${data.max_delivery_time_min} min`;
        kpiRisk.textContent = `${data.high_risk_count} orders`;

        batchDownloadBtn.href = `${API_BASE}/api/download-batch/${data.download_id}`;
        batchDownloadBtn.textContent = `⬇ Download ${data.filename}`;

        batchTableBody.innerHTML = "";
        data.preview.forEach((row) => {
          const tr = document.createElement("tr");

          let statusClass = "status-fast";
          if (row.Delivery_Status_Risk === "High Delay Risk") {
            statusClass = "status-risk";
          } else if (row.Delivery_Status_Risk === "Standard / Medium Risk") {
            statusClass = "status-std";
          }

          tr.innerHTML = `
            <td>${row.Distance_km}</td>
            <td>${row.Weather}</td>
            <td>${row.Traffic_Level}</td>
            <td>${row.Time_of_Day}</td>
            <td>${row.Vehicle_Type}</td>
            <td>${row.Preparation_Time_min} min</td>
            <td>${row.Courier_Experience_yrs} yrs</td>
            <td class="highlight-col">${Number(row.Predicted_Delivery_Time_min).toFixed(2)}</td>
            <td><span class="status-pill ${statusClass}">${row.Delivery_Status_Risk}</span></td>
          `;
          batchTableBody.appendChild(tr);
        });

        batchResultsSection.classList.remove("hidden");
        loadOrderHistory(true);
      }
    } catch (err) {
      batchErrorMessage.textContent = `Batch upload error: ${err.message}`;
      batchErrorCard.classList.remove("hidden");
    } finally {
      setBatchLoading(false);
    }
  });

  // =========================================================================
  // 6. Tab 3: Hotel Model Retraining Controller
  // =========================================================================
  const retrainForm = document.getElementById("retrain-form");
  const retrainFileInput = document.getElementById("retrain-file-input");
  const retrainFilenameDisplay = document.getElementById("retrain-filename-display");
  const hotelNameInput = document.getElementById("hotel-name-input");
  const retrainSubmitBtn = document.getElementById("retrain-submit-btn");
  const retrainSpinner = document.getElementById("retrain-spinner");
  const retrainBtnText = retrainSubmitBtn.querySelector(".btn-text");

  const retrainResultsSection = document.getElementById("retrain-results-section");
  const retrainErrorCard = document.getElementById("retrain-error-card");
  const retrainErrorMessage = document.getElementById("retrain-error-message");

  const retrainSamples = document.getElementById("retrain-samples");
  const retrainMae = document.getElementById("retrain-mae");
  const retrainR2 = document.getElementById("retrain-r2");
  const retrainLift = document.getElementById("retrain-lift");
  const retrainSuccessDesc = document.getElementById("retrain-success-desc");

  retrainFileInput.addEventListener("change", () => {
    if (retrainFileInput.files.length > 0) {
      const file = retrainFileInput.files[0];
      retrainFilenameDisplay.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
      retrainFilenameDisplay.classList.remove("hidden");
      retrainSubmitBtn.disabled = false;
    } else {
      retrainFilenameDisplay.classList.add("hidden");
      retrainSubmitBtn.disabled = true;
    }
  });

  function setRetrainLoading(isLoading) {
    if (isLoading) {
      retrainSubmitBtn.disabled = true;
      retrainSpinner.classList.remove("hidden");
      retrainBtnText.textContent = "Executing automated cleaning, feature engineering & training...";
      retrainErrorCard.classList.add("hidden");
      retrainResultsSection.classList.add("hidden");
    } else {
      retrainSubmitBtn.disabled = false;
      retrainSpinner.classList.add("hidden");
      retrainBtnText.textContent = "Execute Automated Retraining Pipeline";
    }
  }

  retrainForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!retrainFileInput.files.length) return;

    setRetrainLoading(true);

    const formData = new FormData();
    formData.append("file", retrainFileInput.files[0]);
    formData.append("hotel_name", hotelNameInput.value.trim() || "My Hotel / Merchant");

    try {
      const response = await fetch(`${API_BASE}/api/retrain-hotel-model`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        retrainErrorMessage.textContent = data.detail || "Automated retraining failed.";
        retrainErrorCard.classList.remove("hidden");
      } else {
        const m = data.metrics;
        retrainSamples.textContent = `${m.train_samples} / ${m.test_samples}`;
        retrainMae.textContent = `${m.model_mae} min`;
        retrainR2.textContent = `${m.model_r2}`;
        retrainLift.textContent = `${m.mae_improvement_vs_baseline_pct} Lift`;
        retrainSuccessDesc.textContent = `Trained model saved to models/custom_hotel_pipeline.joblib. Baseline MAE: ${m.baseline_mae}m ➔ New Model MAE: ${m.model_mae}m (5-Fold CV MAE: ${m.cv_mae}m).`;

        retrainResultsSection.classList.remove("hidden");
      }
    } catch (err) {
      retrainErrorMessage.textContent = `Retraining pipeline error: ${err.message}`;
      retrainErrorCard.classList.remove("hidden");
    } finally {
      setRetrainLoading(false);
    }
  });

  // =========================================================================
  // 7. Tab 4: SQLite Order History Controller
  // =========================================================================
  const historyTableBody = document.getElementById("history-table-body");
  const historyEmptyState = document.getElementById("history-empty-state");
  const historyCountBadge = document.getElementById("history-count-badge");
  const refreshHistoryBtn = document.getElementById("refresh-history-btn");
  const exportHistoryBtn = document.getElementById("export-history-btn");
  const clearHistoryBtn = document.getElementById("clear-history-btn");

  let currentHistoryData = [];

  async function loadOrderHistory(badgeOnly = false) {
    try {
      const res = await fetch(`${API_BASE}/api/order-history?limit=100`);
      if (!res.ok) return;
      const data = await res.json();

      historyCountBadge.textContent = data.total;
      currentHistoryData = data.orders || [];

      if (badgeOnly) return;

      if (!currentHistoryData.length) {
        historyTableBody.innerHTML = "";
        historyEmptyState.classList.remove("hidden");
        return;
      }

      historyEmptyState.classList.add("hidden");
      historyTableBody.innerHTML = "";

      currentHistoryData.forEach((order) => {
        const tr = document.createElement("tr");

        let statusClass = "status-fast";
        if (order.risk_status === "High Delay Risk") {
          statusClass = "status-risk";
        } else if (order.risk_status === "Standard / Medium Risk") {
          statusClass = "status-std";
        }

        const formattedTime = order.created_at
          ? order.created_at.replace("T", " ").substring(0, 19)
          : "-";

        const destinationDisplay = order.destination_address || "Standard Area";

        tr.innerHTML = `
          <td>#${order.id}</td>
          <td>${formattedTime}</td>
          <td style="max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${destinationDisplay}">${destinationDisplay}</td>
          <td>${order.distance_km} km</td>
          <td>${order.weather}</td>
          <td>${order.traffic_level}</td>
          <td>${order.vehicle_type}</td>
          <td>${order.prep_time_min}m</td>
          <td>${order.courier_exp_yrs}y</td>
          <td class="highlight-col">${Number(order.predicted_time_min).toFixed(2)} min</td>
          <td><span class="status-pill ${statusClass}">${order.risk_status}</span></td>
          <td><span style="font-size:0.75rem; text-transform:uppercase; color:#64748b; font-weight:600;">${order.source_type}</span></td>
        `;
        historyTableBody.appendChild(tr);
      });
    } catch (err) {
      console.warn("Could not load history from SQLite:", err);
    }
  }

  refreshHistoryBtn.addEventListener("click", () => loadOrderHistory(false));

  exportHistoryBtn.addEventListener("click", () => {
    if (!currentHistoryData.length) {
      alert("No history records to export.");
      return;
    }

    const headers = ["ID", "Time_Logged", "Destination", "Distance_km", "Weather", "Traffic_Level", "Time_of_Day", "Vehicle_Type", "Prep_Time_min", "Courier_Experience_yrs", "Predicted_Time_min", "Risk_Status", "Source_Type"];
    const csvRows = [headers.join(",")];

    currentHistoryData.forEach((row) => {
      const vals = [
        row.id,
        `"${row.created_at}"`,
        `"${(row.destination_address || '').replace(/"/g, '""')}"`,
        row.distance_km,
        `"${row.weather}"`,
        `"${row.traffic_level}"`,
        `"${row.time_of_day}"`,
        `"${row.vehicle_type}"`,
        row.prep_time_min,
        row.courier_exp_yrs,
        row.predicted_time_min,
        `"${row.risk_status}"`,
        `"${row.source_type}"`,
      ];
      csvRows.push(vals.join(","));
    });

    const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `order_predictions_history_${new Date().toISOString().substring(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  });

  clearHistoryBtn.addEventListener("click", async () => {
    if (!confirm("Are you sure you want to clear all prediction history records from SQLite?")) {
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/order-history`, { method: "DELETE" });
      if (res.ok) {
        loadOrderHistory(false);
      }
    } catch (err) {
      alert(`Error clearing history: ${err.message}`);
    }
  });

  // =========================================================================
  // 8. Rider Fleet & Live GPS Management Controller
  // =========================================================================
  const ridersTab = document.getElementById("riders-tab");
  const ridersCountBadge = document.getElementById("riders-count-badge");
  const ridersCardContainer = document.getElementById("riders-card-container");
  const ridersEmptyState = document.getElementById("riders-empty-state");

  const statTotalRiders = document.getElementById("stat-total-riders");
  const statAvailRiders = document.getElementById("stat-avail-riders");
  const statOnDeliveryRiders = document.getElementById("stat-ondelivery-riders");
  const statAvgExp = document.getElementById("stat-avg-exp");

  const riderRegisterForm = document.getElementById("rider-register-form");
  const riderNameInput = document.getElementById("rider-name-input");
  const riderPhoneInput = document.getElementById("rider-phone-input");
  const riderVehicleInput = document.getElementById("rider-vehicle-input");
  const riderExpInput = document.getElementById("rider-exp-input");
  const riderAddressInput = document.getElementById("rider-address-input");
  const riderLatInput = document.getElementById("rider-lat-input");
  const riderLngInput = document.getElementById("rider-lng-input");
  const riderStatusInput = document.getElementById("rider-status-input");
  const riderRatingInput = document.getElementById("rider-rating-input");
  const btnDetectRiderGps = document.getElementById("btn-detect-rider-gps");
  const riderGpsStatusHint = document.getElementById("rider-gps-status-hint");
  const btnSubmitRider = document.getElementById("btn-submit-rider");
  const riderSpinner = document.getElementById("rider-spinner");

  const assignRiderSelect = document.getElementById("assign-rider-select");
  const assignedRiderBadge = document.getElementById("assigned-rider-badge");

  let currentRidersFleet = [];
  let currentFleetFilter = "all";

  // Auto GPS Detection for Rider
  if (btnDetectRiderGps) {
    btnDetectRiderGps.addEventListener("click", () => {
      if (!navigator.geolocation) {
        if (riderGpsStatusHint) {
          riderGpsStatusHint.textContent = "⚠️ Geolocation not supported by browser. Using hotel base station.";
          riderGpsStatusHint.style.color = "#dc2626";
        }
        fallbackToHotelCoordinates();
        return;
      }

      if (riderGpsStatusHint) {
        riderGpsStatusHint.textContent = "⏳ Requesting device GPS coordinates...";
        riderGpsStatusHint.style.color = "var(--primary)";
      }

      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const lat = parseFloat(position.coords.latitude.toFixed(6));
          const lng = parseFloat(position.coords.longitude.toFixed(6));
          if (riderLatInput) riderLatInput.value = lat;
          if (riderLngInput) riderLngInput.value = lng;

          if (riderGpsStatusHint) {
            riderGpsStatusHint.textContent = `✅ Device GPS Locked: [${lat}, ${lng}] (Accuracy: ~${Math.round(position.coords.accuracy)}m)`;
            riderGpsStatusHint.style.color = "#059669";
          }

          if (riderAddressInput && !riderAddressInput.value.trim()) {
            try {
              const res = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`, {
                headers: { "Accept-Language": "en" }
              });
              if (res.ok) {
                const data = await res.json();
                if (data && data.display_name) {
                  riderAddressInput.value = data.display_name.split(",").slice(0, 3).join(",").trim();
                }
              }
            } catch (_) {
              riderAddressInput.value = `Live GPS Location (${lat}, ${lng})`;
            }
          }
        },
        (error) => {
          console.warn("Geolocation warning:", error.message);
          fallbackToHotelCoordinates();
          if (riderGpsStatusHint) {
            riderGpsStatusHint.textContent = `ℹ️ GPS permission denied/timed out. Using hotel base location: [${hotelState.lat}, ${hotelState.lng}]`;
            riderGpsStatusHint.style.color = "#d97706";
          }
        },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
      );
    });
  }

  function fallbackToHotelCoordinates() {
    if (riderLatInput && !riderLatInput.value) {
      riderLatInput.value = hotelState.lat || 24.838519;
    }
    if (riderLngInput && !riderLngInput.value) {
      riderLngInput.value = hotelState.lng || 67.081033;
    }
    if (riderAddressInput && !riderAddressInput.value) {
      riderAddressInput.value = hotelState.address || "Station near Hotel Hub";
    }
  }

  // Load Fleet Summary Stats
  async function loadFleetStats() {
    try {
      const res = await fetch(`${API_BASE}/api/fleet/stats`);
      if (!res.ok) return;
      const data = await res.json();
      const stats = data.stats || data;

      if (statTotalRiders) statTotalRiders.textContent = stats.total_riders || 0;
      if (statAvailRiders) statAvailRiders.textContent = stats.available_riders || 0;
      if (statOnDeliveryRiders) statOnDeliveryRiders.textContent = stats.on_delivery_riders || 0;
      if (statAvgExp) statAvgExp.textContent = `${stats.avg_exp_yrs || 0} yrs`;
    } catch (e) {
      console.warn("Could not load fleet stats:", e);
    }
  }

  // Load Riders List
  async function loadRidersList() {
    try {
      const res = await fetch(`${API_BASE}/api/riders`);
      if (!res.ok) return;
      const data = await res.json();
      currentRidersFleet = data.riders || [];

      if (ridersCountBadge) {
        ridersCountBadge.textContent = currentRidersFleet.length;
      }

      populateAssignRiderSelect();
      renderRidersCards();
    } catch (e) {
      console.warn("Could not load riders fleet:", e);
    }
  }

  function populateAssignRiderSelect() {
    if (!assignRiderSelect) return;
    const currentVal = assignRiderSelect.value;
    assignRiderSelect.innerHTML = `<option value="">-- Manual Input (or pick courier to auto-fill vehicle & experience) --</option>`;

    currentRidersFleet.forEach((rider) => {
      const opt = document.createElement("option");
      opt.value = rider.id;
      const statusIcon = rider.status === "Available" ? "🟢" : (rider.status === "On Delivery" ? "📦" : "⚪");
      opt.textContent = `${statusIcon} ${rider.rider_name} (${rider.vehicle_type}, ${rider.courier_exp_yrs} yrs exp) - ${rider.status}`;
      assignRiderSelect.appendChild(opt);
    });

    if (currentVal) assignRiderSelect.value = currentVal;
  }

  if (assignRiderSelect) {
    assignRiderSelect.addEventListener("change", () => {
      const selectedId = parseInt(assignRiderSelect.value, 10);
      if (!selectedId) {
        if (assignedRiderBadge) assignedRiderBadge.textContent = "Live Fleet";
        return;
      }

      const rider = currentRidersFleet.find((r) => r.id === selectedId);
      if (rider) {
        if (vehicleSelect) vehicleSelect.value = rider.vehicle_type;
        if (experienceInput) experienceInput.value = rider.courier_exp_yrs;
        if (assignedRiderBadge) {
          assignedRiderBadge.textContent = `✓ ${rider.rider_name} Assigned`;
        }
      }
    });
  }

  function renderRidersCards() {
    if (!ridersCardContainer) return;
    ridersCardContainer.innerHTML = "";

    const filtered = currentRidersFleet.filter((r) => {
      if (currentFleetFilter === "all") return true;
      return (r.status || "").toLowerCase() === currentFleetFilter.toLowerCase();
    });

    if (filtered.length === 0) {
      if (ridersEmptyState) ridersEmptyState.classList.remove("hidden");
      return;
    } else {
      if (ridersEmptyState) ridersEmptyState.classList.add("hidden");
    }

    filtered.forEach((rider) => {
      const card = document.createElement("div");
      card.className = "rider-card";

      const vehicleIcon = rider.vehicle_type === "Car" ? "🚗" : (rider.vehicle_type === "Bike" ? "🏍️" : "🛵");
      const statusClass = rider.status === "Available"
        ? "status-badge-available"
        : (rider.status === "On Delivery" ? "status-badge-ondelivery" : "status-badge-offline");

      card.innerHTML = `
        <div class="rider-card-top">
          <div class="rider-card-profile">
            <div class="rider-avatar">${vehicleIcon}</div>
            <div>
              <div class="rider-meta-name">${rider.rider_name}</div>
              <div class="rider-meta-phone">📞 ${rider.phone || "No phone"}</div>
            </div>
          </div>
          <span class="rider-status-badge ${statusClass}">${rider.status}</span>
        </div>

        <div class="rider-details-grid">
          <div class="rider-detail-item">
            <div class="val">${rider.vehicle_type}</div>
            <div class="lbl">Vehicle</div>
          </div>
          <div class="rider-detail-item">
            <div class="val">${rider.courier_exp_yrs} yrs</div>
            <div class="lbl">Experience</div>
          </div>
          <div class="rider-detail-item">
            <div class="val">⭐ ${Number(rider.rating || 4.8).toFixed(1)}</div>
            <div class="lbl">Rating</div>
          </div>
        </div>

        <div class="rider-loc-row">
          <span class="rider-loc-icon">&#128205;</span>
          <div>
            <div style="font-weight: 600; color: var(--text-main); font-size: 0.78rem;">
              ${rider.current_address || "Hub Base Station"}
            </div>
            <div style="font-size: 0.7rem; color: #64748b;">
              GPS: [${Number(rider.current_lat || 0).toFixed(4)}, ${Number(rider.current_lng || 0).toFixed(4)}]
            </div>
          </div>
        </div>

        <div class="rider-actions-row">
          <select class="rider-status-select" data-rider-id="${rider.id}">
            <option value="Available" ${rider.status === "Available" ? "selected" : ""}>🟢 Available</option>
            <option value="On Delivery" ${rider.status === "On Delivery" ? "selected" : ""}>📦 On Delivery</option>
            <option value="Offline" ${rider.status === "Offline" ? "selected" : ""}>⚪ Offline</option>
          </select>

          <div style="display: flex; gap: 0.35rem;">
            <button type="button" class="rider-action-btn btn-rider-loc-refresh" data-rider-id="${rider.id}" title="Refresh courier GPS to current station">
              📍 Ping GPS
            </button>
            <button type="button" class="rider-action-btn btn-rider-delete" data-rider-id="${rider.id}" title="Remove courier from registry">
              🗑️
            </button>
          </div>
        </div>
      `;

      // Status change listener
      const statusSelect = card.querySelector(".rider-status-select");
      if (statusSelect) {
        statusSelect.addEventListener("change", async (e) => {
          const newStatus = e.target.value;
          try {
            const resp = await fetch(`${API_BASE}/api/riders/${rider.id}/status`, {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ status: newStatus }),
            });
            if (resp.ok) {
              await loadRidersList();
              await loadFleetStats();
            }
          } catch (err) {
            console.error("Status update error:", err);
          }
        });
      }

      // Ping GPS listener
      const pingBtn = card.querySelector(".btn-rider-loc-refresh");
      if (pingBtn) {
        pingBtn.addEventListener("click", () => {
          if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(async (pos) => {
              const pingLat = parseFloat(pos.coords.latitude.toFixed(6));
              const pingLng = parseFloat(pos.coords.longitude.toFixed(6));
              await fetch(`${API_BASE}/api/riders/${rider.id}/location`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  current_lat: pingLat,
                  current_lng: pingLng,
                  current_address: `Live Ping Station (${pingLat}, ${pingLng})`,
                }),
              });
              loadRidersList();
            });
          }
        });
      }

      // Delete listener
      const delBtn = card.querySelector(".btn-rider-delete");
      if (delBtn) {
        delBtn.addEventListener("click", async () => {
          if (!confirm(`Remove courier ${rider.rider_name} from active fleet?`)) return;
          try {
            const delResp = await fetch(`${API_BASE}/api/riders/${rider.id}`, { method: "DELETE" });
            if (delResp.ok) {
              await loadRidersList();
              await loadFleetStats();
            }
          } catch (delErr) {
            console.error("Delete error:", delErr);
          }
        });
      }

      ridersCardContainer.appendChild(card);
    });
  }

  // Filter Buttons
  const fleetFilterBtns = document.querySelectorAll(".fleet-filter-btn");
  fleetFilterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      fleetFilterBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentFleetFilter = btn.getAttribute("data-filter") || "all";
      renderRidersCards();
    });
  });

  // Rider Registration Form Submission
  if (riderRegisterForm) {
    riderRegisterForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const nameVal = riderNameInput ? riderNameInput.value.trim() : "";
      const phoneVal = riderPhoneInput ? riderPhoneInput.value.trim() : "";
      if (!nameVal || !phoneVal) {
        alert("Please provide the courier name and phone number.");
        return;
      }

      const payload = {
        rider_name: nameVal,
        phone: phoneVal,
        vehicle_type: riderVehicleInput ? riderVehicleInput.value : "Scooter",
        courier_exp_yrs: parseFloat(riderExpInput ? riderExpInput.value : "2.5") || 2.5,
        rating: parseFloat(riderRatingInput ? riderRatingInput.value : "4.8") || 4.8,
        status: riderStatusInput ? riderStatusInput.value : "Available",
        current_address: riderAddressInput ? riderAddressInput.value.trim() : "",
        current_lat: riderLatInput && riderLatInput.value ? parseFloat(riderLatInput.value) : null,
        current_lng: riderLngInput && riderLngInput.value ? parseFloat(riderLngInput.value) : null,
      };

      if (btnSubmitRider) btnSubmitRider.disabled = true;
      if (riderSpinner) riderSpinner.classList.remove("hidden");

      try {
        const res = await fetch(`${API_BASE}/api/riders`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (res.ok) {
          riderRegisterForm.reset();
          if (riderGpsStatusHint) {
            riderGpsStatusHint.textContent = `✅ Courier ${payload.rider_name} successfully registered in fleet!`;
            riderGpsStatusHint.style.color = "#059669";
          }
          await loadRidersList();
          await loadFleetStats();
        } else {
          const errData = await res.json();
          alert(`Could not register rider: ${errData.detail || "Validation error"}`);
        }
      } catch (err) {
        alert(`Network error registering rider: ${err.message}`);
      } finally {
        if (btnSubmitRider) btnSubmitRider.disabled = false;
        if (riderSpinner) riderSpinner.classList.add("hidden");
      }
    });
  }

  // Initialize hotel profile, riders fleet, and history badge on page load
  loadHotelProfile();
  loadOrderHistory(true);
  loadRidersList();
  loadFleetStats();
});

