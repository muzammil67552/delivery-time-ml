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
  let currentDestinationLabel = "Customer Destination";
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

  // Hamburger Profile Menu & Session Logout Elements
  const btnNavbarHamburger = document.getElementById("btn-navbar-hamburger");
  const hotelProfileDropdown = document.getElementById("hotel-profile-dropdown");
  const navbarHotelPillText = document.getElementById("navbar-hotel-pill-text");
  const dropdownModelBadge = document.getElementById("dropdown-model-badge");
  const dropdownCityBadge = document.getElementById("dropdown-city-badge");
  const dropdownHotelName = document.getElementById("dropdown-hotel-name");
  const dropdownHotelAddressText = document.getElementById("dropdown-hotel-address-text");
  const dropdownPrepPill = document.getElementById("dropdown-prep-pill");
  const dropdownVehiclePill = document.getElementById("dropdown-vehicle-pill");
  const menuBtnRetrain = document.getElementById("menu-btn-retrain");
  const menuBtnRiders = document.getElementById("menu-btn-riders");
  const menuBtnDispatch = document.getElementById("menu-btn-dispatch");
  const menuBtnLogout = document.getElementById("menu-btn-logout");

  function toggleHotelProfileDropdown(forceState) {
    if (!hotelProfileDropdown || !btnNavbarHamburger) return;
    const shouldOpen = typeof forceState === "boolean" 
      ? forceState 
      : !hotelProfileDropdown.classList.contains("open");
    
    if (shouldOpen) {
      hotelProfileDropdown.classList.add("open");
      btnNavbarHamburger.classList.add("active");
      btnNavbarHamburger.setAttribute("aria-expanded", "true");
    } else {
      hotelProfileDropdown.classList.remove("open");
      btnNavbarHamburger.classList.remove("active");
      btnNavbarHamburger.setAttribute("aria-expanded", "false");
    }
  }

  if (btnNavbarHamburger) {
    btnNavbarHamburger.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleHotelProfileDropdown();
    });
  }

  // Close dropdown on outside click
  document.addEventListener("click", (e) => {
    if (hotelProfileDropdown && hotelProfileDropdown.classList.contains("open")) {
      if (!hotelProfileDropdown.contains(e.target) && !btnNavbarHamburger.contains(e.target)) {
        toggleHotelProfileDropdown(false);
      }
    }
  });

  // Close dropdown on Escape key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && hotelProfileDropdown && hotelProfileDropdown.classList.contains("open")) {
      toggleHotelProfileDropdown(false);
    }
  });

  // Navigation shortcuts inside hamburger menu
  if (menuBtnRetrain) {
    menuBtnRetrain.addEventListener("click", () => {
      toggleHotelProfileDropdown(false);
      const retrainTabBtn = document.getElementById("tab-retrain");
      if (retrainTabBtn) retrainTabBtn.click();
    });
  }

  if (menuBtnRiders) {
    menuBtnRiders.addEventListener("click", () => {
      toggleHotelProfileDropdown(false);
      const ridersTabBtn = document.getElementById("tab-riders");
      if (ridersTabBtn) ridersTabBtn.click();
    });
  }

  if (menuBtnDispatch) {
    menuBtnDispatch.addEventListener("click", () => {
      toggleHotelProfileDropdown(false);
      const dispatchTabBtn = document.getElementById("tab-dispatch");
      if (dispatchTabBtn) dispatchTabBtn.click();
    });
  }

  // Log Out Session Action
  async function performHotelLogout() {
    try {
      await fetch(`${API_BASE}/api/hotel-logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
    } catch (err) {
      console.warn("Server logout notification failed, continuing local clear:", err);
    }
    // Clear localStorage session keys
    try {
      localStorage.removeItem("dtml_active_hotel_id");
      localStorage.removeItem("dtml_active_hotel");
      sessionStorage.clear();
    } catch (e) {}
    // Clear cookie
    document.cookie = "active_hotel_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    // Redirect to onboarding & login page
    window.location.href = "/welcome";
  }

  if (menuBtnLogout) {
    menuBtnLogout.addEventListener("click", (e) => {
      e.preventDefault();
      toggleHotelProfileDropdown(false);
      performHotelLogout();
    });
  }

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
  // Load existing hotel profile on startup (silently with sensible defaults)
  async function loadHotelProfile() {
    await loadCityPresets();
    try {
      const activeHotelId = localStorage.getItem("dtml_active_hotel_id");
      const url = activeHotelId ? `${API_BASE}/api/hotel-profile?hotel_id=${encodeURIComponent(activeHotelId)}` : `${API_BASE}/api/hotel-profile`;
      const res = await fetch(url, {
        headers: activeHotelId ? { "X-Hotel-ID": String(activeHotelId) } : {}
      });
      if (!res.ok) {
        initMap();
        renderLandmarkPills();
        return;
      }
      const data = await res.json();

      if (data.is_configured && data.profile) {
        const p = data.profile;
        if (p.id) {
          try {
            localStorage.setItem("dtml_active_hotel_id", String(p.id));
            localStorage.setItem("dtml_active_hotel", p.hotel_name || "");
          } catch (e) {}
        }
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

        // Update Navbar Hamburger Pill Text (compact, prevents desktop horizontal scrollbar)
        if (navbarHotelPillText) {
          navbarHotelPillText.textContent = p.hotel_name || "Hotel Profile";
          navbarHotelPillText.title = `${p.hotel_name || ''} - ${p.branch_or_address || ''}`;
        }
        if (navbarHotelName) {
          navbarHotelName.textContent = p.hotel_name || "Hotel Profile";
        }

        // Update Complete Hotel Details inside the Hamburger Dropdown Menu
        if (dropdownHotelName) {
          dropdownHotelName.textContent = p.hotel_name || "Hotel Express Hub";
        }
        if (dropdownHotelAddressText) {
          dropdownHotelAddressText.textContent = p.branch_or_address || `${hotelState.city_preset} Operational Hub`;
        }
        if (dropdownCityBadge) {
          dropdownCityBadge.textContent = `${p.city_preset || "New York"} Hub`;
        }
        if (dropdownPrepPill) {
          dropdownPrepPill.innerHTML = `&#9201; ${p.default_prep_time_min || 15} min prep`;
        }
        if (dropdownVehiclePill) {
          dropdownVehiclePill.innerHTML = `&#128757; ${p.default_vehicle_type || "Scooter"}`;
        }
        if (dropdownModelBadge) {
          if (p.has_custom_model) {
            dropdownModelBadge.innerHTML = "&#11088; Custom Model";
            dropdownModelBadge.style.background = "#ecfdf5";
            dropdownModelBadge.style.color = "#047857";
            dropdownModelBadge.style.borderColor = "#a7f3d0";
          } else {
            dropdownModelBadge.innerHTML = "&#9889; Production Model";
            dropdownModelBadge.style.background = "#eef2ff";
            dropdownModelBadge.style.color = "#4338ca";
            dropdownModelBadge.style.borderColor = "#c7d2fe";
          }
        }
        if (navbarModelBadge) {
          navbarModelBadge.innerHTML = dropdownModelBadge ? dropdownModelBadge.innerHTML : "&#9889; Production Model";
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
      const activeHotelId = localStorage.getItem("dtml_active_hotel_id");
      const payload = {
        id: activeHotelId ? parseInt(activeHotelId, 10) : undefined,
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
        const headers = { "Content-Type": "application/json" };
        if (activeHotelId) {
          headers["X-Hotel-ID"] = String(activeHotelId);
        }
        const res = await fetch(`${API_BASE}/api/hotel-profile`, {
          method: "POST",
          headers: headers,
          body: JSON.stringify(payload),
        });

        if (res.ok) {
          const data = await res.json();
          const p = data.profile;
          if (p.id) {
            try {
              localStorage.setItem("dtml_active_hotel_id", String(p.id));
              localStorage.setItem("dtml_active_hotel", p.hotel_name || "");
            } catch (e) {}
          }
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
    if (addressLabel) {
      currentDestinationLabel = addressLabel;
    }

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

      const targetId = btn.getAttribute("data-tab");
      // Synchronize all tab buttons matching this target (both desktop top nav and mobile bottom nav)
      document.querySelectorAll(`.tab-btn[data-tab="${targetId}"]`).forEach((b) => b.classList.add("active"));

      const targetTab = document.getElementById(targetId);
      if (targetTab) {
        targetTab.classList.remove("hidden");
      }

      // Smooth scroll to top on mobile app navigation
      if (window.innerWidth <= 860) {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }

      if (targetId === "history-tab") {
        loadOrderHistory();
      }

      if (targetId === "riders-tab") {
        loadRidersList();
        loadFleetStats();
        requestNativeSensorTracking(false);
      }

      if (targetId === "dispatch-tab") {
        fetchNewTrackingId();
        updateEnrichmentPreview();
        loadRecentDispatches();
        loadRawMlData();
      }

      // Re-invalidate Leaflet map size on tab switch
      if (targetId === "single-tab" && map) {
        setTimeout(() => map.invalidateSize(), 150);
      }
    });
  });

  // Keep Leaflet map geometry sharp on viewport resize
  window.addEventListener("resize", () => {
    if (map) {
      map.invalidateSize();
    }
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
      Destination_Address: (destinationAddressInput && destinationAddressInput.value)
        ? destinationAddressInput.value
        : (currentDestinationLabel || (currentDestLat ? `Dropoff (${currentDestLat.toFixed(4)}, ${currentDestLng.toFixed(4)})` : "Customer Destination")),
      Dropoff_Lat: currentDestLat,
      Dropoff_Lng: currentDestLng,
    };

    const valErr = validateSingleInputs(payload);
    if (valErr) {
      showSingleError(valErr);
      return;
    }

    const activeHotelId = localStorage.getItem("dtml_active_hotel_id");
    if (activeHotelId) {
      payload.Hotel_ID = parseInt(activeHotelId, 10);
    }

    setSingleLoading(true);

    try {
      const predHeaders = { "Content-Type": "application/json" };
      if (activeHotelId) {
        predHeaders["X-Hotel-ID"] = String(activeHotelId);
      }
      const response = await fetch(`${API_BASE}/predict`, {
        method: "POST",
        headers: predHeaders,
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
      const activeHotelId = localStorage.getItem("dtml_active_hotel_id");
      const url = activeHotelId 
        ? `${API_BASE}/api/order-history?limit=100&hotel_id=${encodeURIComponent(activeHotelId)}` 
        : `${API_BASE}/api/order-history?limit=100`;
      const res = await fetch(url, {
        headers: activeHotelId ? { "X-Hotel-ID": String(activeHotelId) } : {}
      });
      if (!res.ok) return;
      const data = await res.json();

      if (historyCountBadge) historyCountBadge.textContent = data.total;
      const bnavHistoryBadge = document.getElementById("bnav-history-badge");
      if (bnavHistoryBadge) bnavHistoryBadge.textContent = data.total;
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
    if (!confirm("Are you sure you want to clear all prediction history records from SQLite for this hotel?")) {
      return;
    }

    try {
      const activeHotelId = localStorage.getItem("dtml_active_hotel_id");
      const url = activeHotelId ? `${API_BASE}/api/order-history?hotel_id=${encodeURIComponent(activeHotelId)}` : `${API_BASE}/api/order-history`;
      const res = await fetch(url, {
        method: "DELETE",
        headers: activeHotelId ? { "X-Hotel-ID": String(activeHotelId) } : {}
      });
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
  const riderEmailInput = document.getElementById("rider-email-input");
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

  // Native GPS Sensor Auto-Tracking Controller (Hardware-Free)
  const gpsSensorPanel = document.getElementById("gps-sensor-panel");
  const sensorStatusLabel = document.getElementById("sensor-status-label");
  const permissionStateBadge = document.getElementById("permission-state-badge");
  const btnRequestSensorPerm = document.getElementById("btn-request-sensor-perm");
  const sensorTelemetryStrip = document.getElementById("sensor-telemetry-strip");
  const telemetryLat = document.getElementById("telemetry-lat");
  const telemetryLng = document.getElementById("telemetry-lng");
  const telemetryAcc = document.getElementById("telemetry-acc");

  let activeSensorWatchId = null;
  let lastSensorCoords = null;
  let activeCourierRiderId = localStorage.getItem("active_device_rider_id") || null;

  function requestNativeSensorTracking(userInitiated = false) {
    if (!navigator.geolocation) {
      if (sensorStatusLabel) {
        sensorStatusLabel.textContent = "⚠️ Native GPS Sensor not supported by browser. Using station coordinates.";
        sensorStatusLabel.style.color = "#dc2626";
      }
      if (permissionStateBadge) {
        permissionStateBadge.textContent = "Unsupported";
        permissionStateBadge.style.background = "#fee2e2";
        permissionStateBadge.style.color = "#991b1b";
      }
      if (riderGpsStatusHint) {
        riderGpsStatusHint.textContent = "⚠️ Geolocation not supported by browser. Using hotel base station.";
        riderGpsStatusHint.style.color = "#dc2626";
      }
      fallbackToHotelCoordinates();
      return;
    }

    if (sensorStatusLabel) {
      sensorStatusLabel.textContent = "📡 Native Device GPS Sensor: Requesting Live Permission...";
      sensorStatusLabel.style.color = "var(--primary)";
    }
    if (permissionStateBadge) {
      permissionStateBadge.textContent = "Prompting...";
      permissionStateBadge.style.background = "#fef3c7";
      permissionStateBadge.style.color = "#b45309";
    }
    if (riderGpsStatusHint) {
      riderGpsStatusHint.textContent = "⏳ Requesting device GPS coordinates (Please select 'Allow all the time')...";
      riderGpsStatusHint.style.color = "var(--primary)";
    }

    navigator.geolocation.getCurrentPosition(
      onSensorPositionSuccess,
      (err) => onSensorPositionError(err, userInitiated),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
    );

    // Continuous real-time native sensor watch
    if (activeSensorWatchId === null) {
      try {
        activeSensorWatchId = navigator.geolocation.watchPosition(
          onSensorPositionSuccess,
          (err) => console.warn("Native sensor continuous watch warning:", err.message),
          { enableHighAccuracy: true, maximumAge: 4000, timeout: 15000 }
        );
      } catch (e) {
        console.warn("Watch position error:", e);
      }
    }
  }

  async function onSensorPositionSuccess(position) {
    const lat = parseFloat(position.coords.latitude.toFixed(6));
    const lng = parseFloat(position.coords.longitude.toFixed(6));
    const acc = Math.round(position.coords.accuracy || 10);
    lastSensorCoords = { lat, lng, acc };

    if (riderLatInput) riderLatInput.value = lat;
    if (riderLngInput) riderLngInput.value = lng;

    if (gpsSensorPanel) gpsSensorPanel.classList.add("sensor-active");
    if (sensorStatusLabel) {
      sensorStatusLabel.textContent = `🟢 Native Device GPS Sensor: ACTIVE (Live Auto-Tracking • ±${acc}m)`;
      sensorStatusLabel.style.color = "#065f46";
    }
    if (permissionStateBadge) {
      permissionStateBadge.textContent = "Granted (Allow All Time / In Use)";
      permissionStateBadge.style.background = "#dcfce7";
      permissionStateBadge.style.color = "#15803d";
    }
    if (btnRequestSensorPerm) {
      btnRequestSensorPerm.innerHTML = "<span>✅ Live Sensor Active</span>";
      btnRequestSensorPerm.style.background = "#059669";
    }
    if (telemetryLat) telemetryLat.textContent = lat;
    if (telemetryLng) telemetryLng.textContent = lng;
    if (telemetryAcc) telemetryAcc.textContent = `±${acc}m`;
    if (sensorTelemetryStrip) sensorTelemetryStrip.classList.remove("hidden");

    if (riderGpsStatusHint) {
      riderGpsStatusHint.textContent = `✅ Live Native GPS Sensor Locked: [${lat}, ${lng}] (Accuracy: ~${acc}m) • Hardware-Free Tracking Active`;
      riderGpsStatusHint.style.color = "#059669";
    }

    if (riderAddressInput && (!riderAddressInput.value.trim() || riderAddressInput.value.startsWith("Live GPS") || riderAddressInput.value.startsWith("Live Native") || riderAddressInput.value.startsWith("Station near"))) {
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

    // Auto background sync to FastAPI if rider is registered on this device
    if (activeCourierRiderId) {
      try {
        await fetch(`${API_BASE}/api/riders/${activeCourierRiderId}/location`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            current_lat: lat,
            current_lng: lng,
            current_address: riderAddressInput && riderAddressInput.value ? riderAddressInput.value : `Live Device Sensor (${lat}, ${lng})`,
          }),
        });
      } catch (_) {}
    }
  }

  function onSensorPositionError(error, userInitiated = false) {
    console.warn("Native geolocation error:", error.code, error.message);
    fallbackToHotelCoordinates();

    if (error.code === 1) { // PERMISSION_DENIED
      if (sensorStatusLabel) {
        sensorStatusLabel.textContent = "⚠️ Location Permission Denied: Allow Delivery App to Access Location";
        sensorStatusLabel.style.color = "#dc2626";
      }
      if (permissionStateBadge) {
        permissionStateBadge.textContent = "Permission Blocked";
        permissionStateBadge.style.background = "#fee2e2";
        permissionStateBadge.style.color = "#991b1b";
      }
      if (riderGpsStatusHint) {
        riderGpsStatusHint.textContent = `⚠️ Location permission denied. Please select "Allow all the time" or "Allow" in your browser address bar/settings to enable hardware-free live tracking. Using hotel base location: [${hotelState.lat}, ${hotelState.lng}]`;
        riderGpsStatusHint.style.color = "#d97706";
      }
      if (userInitiated) {
        alert("Location access was denied. To enable native hardware-free GPS tracking, please click the site settings icon in your browser address bar and choose 'Allow' for Location.");
      }
    } else {
      if (riderGpsStatusHint) {
        riderGpsStatusHint.textContent = `ℹ️ GPS sensor timed out or unavailable. Using hotel base location: [${hotelState.lat}, ${hotelState.lng}]`;
        riderGpsStatusHint.style.color = "#d97706";
      }
    }
  }

  if (btnRequestSensorPerm) {
    btnRequestSensorPerm.addEventListener("click", () => {
      requestNativeSensorTracking(true);
    });
  }

  if (btnDetectRiderGps) {
    btnDetectRiderGps.addEventListener("click", () => {
      requestNativeSensorTracking(true);
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
      const activeHotelId = localStorage.getItem("dtml_active_hotel_id");
      const url = activeHotelId ? `${API_BASE}/api/fleet/stats?hotel_id=${encodeURIComponent(activeHotelId)}` : `${API_BASE}/api/fleet/stats`;
      const res = await fetch(url, {
        headers: activeHotelId ? { "X-Hotel-ID": String(activeHotelId) } : {}
      });
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
      const activeHotelId = localStorage.getItem("dtml_active_hotel_id");
      const url = activeHotelId ? `${API_BASE}/api/riders?hotel_id=${encodeURIComponent(activeHotelId)}` : `${API_BASE}/api/riders`;
      const res = await fetch(url, {
        headers: activeHotelId ? { "X-Hotel-ID": String(activeHotelId) } : {}
      });
      if (!res.ok) return;
      const data = await res.json();
      currentRidersFleet = data.riders || [];

      if (ridersCountBadge) {
        ridersCountBadge.textContent = currentRidersFleet.length;
      }
      const bnavRidersBadge = document.getElementById("bnav-riders-badge");
      if (bnavRidersBadge) {
        bnavRidersBadge.textContent = currentRidersFleet.length;
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
      const emailDisplay = rider.email ? ` [${rider.email}]` : "";
      opt.textContent = `${statusIcon} ${rider.rider_name}${emailDisplay} (${rider.vehicle_type}, ${rider.courier_exp_yrs} yrs exp) - ${rider.status}`;
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
              <div class="rider-meta-email" style="font-size: 0.72rem; color: #4f46e5; font-weight: 500;">✉️ ${rider.email || "No email registered"}</div>
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
          <div style="flex: 1;">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 0.4rem;">
              <span style="font-weight: 600; color: var(--text-main); font-size: 0.78rem;">
                ${rider.current_address || "Hub Base Station"}
              </span>
              <span class="rider-live-gps-badge">
                <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#10b981;"></span>
                Live Native GPS
              </span>
            </div>
            <div style="font-size: 0.7rem; color: #64748b; margin-top: 0.15rem;">
              Coordinates: [${Number(rider.current_lat || 0).toFixed(5)}, ${Number(rider.current_lng || 0).toFixed(5)}]
            </div>
            <a href="https://www.openstreetmap.org/?mlat=${rider.current_lat}&mlon=${rider.current_lng}#map=16/${rider.current_lat}/${rider.current_lng}" target="_blank" rel="noopener" class="rider-card-map-link">
              🗺️ Track on Live Map &rarr;
            </a>
          </div>
        </div>

        <div class="rider-actions-row">
          <select class="rider-status-select" data-rider-id="${rider.id}">
            <option value="Available" ${rider.status === "Available" ? "selected" : ""}>🟢 Available</option>
            <option value="On Delivery" ${rider.status === "On Delivery" ? "selected" : ""}>📦 On Delivery</option>
            <option value="Offline" ${rider.status === "Offline" ? "selected" : ""}>⚪ Offline</option>
          </select>

          <div style="display: flex; gap: 0.35rem;">
            <button type="button" class="rider-action-btn btn-rider-loc-refresh" data-rider-id="${rider.id}" title="Re-sync courier device native GPS sensor">
              📍 Sync Sensor
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

      // Ping GPS listener (hardware-free sensor re-sync)
      const pingBtn = card.querySelector(".btn-rider-loc-refresh");
      if (pingBtn) {
        pingBtn.addEventListener("click", () => {
          if (navigator.geolocation) {
            pingBtn.textContent = "⏳ Syncing...";
            navigator.geolocation.getCurrentPosition(async (pos) => {
              const pingLat = parseFloat(pos.coords.latitude.toFixed(6));
              const pingLng = parseFloat(pos.coords.longitude.toFixed(6));
              let addr = `Live Native Sensor (${pingLat}, ${pingLng})`;
              try {
                const r = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${pingLat}&lon=${pingLng}&format=json`, {
                  headers: { "Accept-Language": "en" }
                });
                if (r.ok) {
                  const d = await r.json();
                  if (d && d.display_name) addr = d.display_name.split(",").slice(0, 3).join(",").trim();
                }
              } catch (_) {}
              await fetch(`${API_BASE}/api/riders/${rider.id}/location`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  current_lat: pingLat,
                  current_lng: pingLng,
                  current_address: addr,
                }),
              });
              pingBtn.textContent = "✅ Synced";
              setTimeout(() => {
                loadRidersList();
              }, 400);
            }, (err) => {
              alert(`Could not read native GPS sensor: ${err.message}`);
              pingBtn.textContent = "📍 Sync Sensor";
            }, { enableHighAccuracy: true, timeout: 8000 });
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

  // Rider Registration Form Submission with Native GPS Auto-Capture
  if (riderRegisterForm) {
    riderRegisterForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const nameVal = riderNameInput ? riderNameInput.value.trim() : "";
      const phoneVal = riderPhoneInput ? riderPhoneInput.value.trim() : "";
      const emailVal = riderEmailInput ? riderEmailInput.value.trim() : "";
      if (!nameVal || !phoneVal || !emailVal) {
        alert("Please provide the courier name, contact phone, and email address.");
        return;
      }

      const latVal = riderLatInput && riderLatInput.value ? parseFloat(riderLatInput.value) : (lastSensorCoords ? lastSensorCoords.lat : null);
      const lngVal = riderLngInput && riderLngInput.value ? parseFloat(riderLngInput.value) : (lastSensorCoords ? lastSensorCoords.lng : null);

      const payload = {
        rider_name: nameVal,
        phone: phoneVal,
        email: emailVal,
        vehicle_type: riderVehicleInput ? riderVehicleInput.value : "Scooter",
        courier_exp_yrs: parseFloat(riderExpInput ? riderExpInput.value : "2.5") || 2.5,
        rating: parseFloat(riderRatingInput ? riderRatingInput.value : "4.8") || 4.8,
        status: riderStatusInput ? riderStatusInput.value : "Available",
        current_address: riderAddressInput ? riderAddressInput.value.trim() : "",
        current_lat: latVal,
        current_lng: lngVal,
      };

      const activeHotelId = localStorage.getItem("dtml_active_hotel_id");
      if (activeHotelId) {
        payload.hotel_id = parseInt(activeHotelId, 10);
      }

      if (btnSubmitRider) btnSubmitRider.disabled = true;
      if (riderSpinner) riderSpinner.classList.remove("hidden");

      try {
        const riderHeaders = { "Content-Type": "application/json" };
        if (activeHotelId) {
          riderHeaders["X-Hotel-ID"] = String(activeHotelId);
        }
        const res = await fetch(`${API_BASE}/api/riders`, {
          method: "POST",
          headers: riderHeaders,
          body: JSON.stringify(payload),
        });

        if (res.ok) {
          const resData = await res.json();
          const savedRider = resData.rider || resData;
          if (savedRider && savedRider.id) {
            activeCourierRiderId = savedRider.id;
            localStorage.setItem("active_device_rider_id", savedRider.id);
          }

          riderRegisterForm.reset();
          // Restore latest coordinates into form inputs so form stays primed
          if (lastSensorCoords) {
            if (riderLatInput) riderLatInput.value = lastSensorCoords.lat;
            if (riderLngInput) riderLngInput.value = lastSensorCoords.lng;
          }

          if (riderGpsStatusHint) {
            riderGpsStatusHint.textContent = `✅ Courier ${payload.rider_name} (${payload.email}) successfully registered! Real-time dispatch emails will be automatically routed to this address.`;
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

  // =========================================================================
  // 9. Automated Dispatch Engine & Cascading Pipeline Controller
  // =========================================================================
  const dispatchTrackingIdInput = document.getElementById("dispatch-tracking-id");
  const btnGenTrackingId = document.getElementById("btn-gen-tracking-id");
  const btnCopyTracking = document.getElementById("btn-copy-tracking");
  const dispatchClientNameInput = document.getElementById("dispatch-client-name");
  const dispatchClientPhoneInput = document.getElementById("dispatch-client-phone");
  const dispatchClientAddressInput = document.getElementById("dispatch-client-address");
  const btnUseMapAddress = document.getElementById("btn-use-map-address");
  const dispatchPrepTimeInput = document.getElementById("dispatch-prep-time");
  const dispatchTrafficLevelInput = document.getElementById("dispatch-traffic-level");
  const dispatchAdminForm = document.getElementById("dispatch-admin-form");
  const btnConfirmDispatch = document.getElementById("btn-confirm-dispatch");
  const dispatchSpinner = document.getElementById("dispatch-spinner");

  // Enrichment Badges
  const valEnrichDistance = document.getElementById("val-enrich-distance");
  const valEnrichWeather = document.getElementById("val-enrich-weather");
  const valEnrichTime = document.getElementById("val-enrich-time");
  const valEnrichProximity = document.getElementById("val-enrich-proximity");

  // Cockpit Elements
  const cockpitStatusChip = document.getElementById("cockpit-status-chip");
  const cockpitEmptyState = document.getElementById("cockpit-empty-state");
  const cockpitActiveSession = document.getElementById("cockpit-active-session");
  const cockpitTrkId = document.getElementById("cockpit-trk-id");
  const cockpitCountdown = document.getElementById("cockpit-countdown");
  const timeoutTimerWidget = document.getElementById("timeout-timer-widget");
  const cockpitRiderAvatar = document.getElementById("cockpit-rider-avatar");
  const cockpitRiderName = document.getElementById("cockpit-rider-name");
  const cockpitRiderEmail = document.getElementById("cockpit-rider-email");
  const cockpitRiderPerf = document.getElementById("cockpit-rider-perf");
  const cockpitDistHotel = document.getElementById("cockpit-dist-hotel");
  const cockpitDeliveryDist = document.getElementById("cockpit-delivery-dist");
  const cockpitPredictedEta = document.getElementById("cockpit-predicted-eta");
  const cockpitAttemptCount = document.getElementById("cockpit-attempt-count");
  const cockpitEmailRecipient = document.getElementById("cockpit-email-recipient");

  // Simulation Controls
  const btnPreviewEmailModal = document.getElementById("btn-preview-email-modal");
  const btnSimActivate = document.getElementById("btn-sim-activate");
  const btnSimDeactivate = document.getElementById("btn-sim-deactivate");
  const btnSimTimeout = document.getElementById("btn-sim-timeout");

  // Delivery Completion
  const deliveryCompletionBox = document.getElementById("delivery-completion-box");
  const inputActualDuration = document.getElementById("input-actual-duration");
  const btnMarkDelivered = document.getElementById("btn-mark-delivered");
  const deliveryResultBanner = document.getElementById("delivery-result-banner");

  // Email Modal
  const emailPreviewModal = document.getElementById("email-preview-modal");
  const btnCloseEmailModal = document.getElementById("btn-close-email-modal");
  const emailIframeWrapper = document.getElementById("email-iframe-wrapper");

  // Sub-tabs & Tables
  const subtabActiveOrders = document.getElementById("subtab-active-orders");
  const subtabRawMl = document.getElementById("subtab-raw-ml");
  const viewActiveOrders = document.getElementById("view-active-orders");
  const viewRawMl = document.getElementById("view-raw-ml");
  const dispatchesTableBody = document.getElementById("dispatches-table-body");
  const rawMlTableBody = document.getElementById("raw-ml-table-body");
  const dispatchCountBadge = document.getElementById("dispatch-count-badge");
  const bnavDispatchBadge = document.getElementById("bnav-dispatch-badge");
  const dispatchTableCount = document.getElementById("dispatch-table-count");
  const rawMlTableCount = document.getElementById("raw-ml-table-count");
  const btnRefreshDispatches = document.getElementById("btn-refresh-dispatches");
  const btnToggleRawMl = document.getElementById("btn-toggle-raw-ml");
  const btnExportRawMl = document.getElementById("btn-export-raw-ml");
  const btnGotoDispatch = document.getElementById("btn-goto-dispatch");

  let activeDispatchSession = null;
  let countdownTimer = null;
  let cachedEmailHtml = "";

  // 1. Fetch Fresh Unique Tracking ID
  async function fetchNewTrackingId() {
    try {
      const res = await fetch(`${API_BASE}/api/dispatch/generate-tracking-id`);
      if (res.ok) {
        const data = await res.json();
        if (dispatchTrackingIdInput) {
          dispatchTrackingIdInput.value = data.tracking_id;
        }
      }
    } catch (_) {
      const fallback = `TRK-${Math.floor(100000 + Math.random() * 900000)}`;
      if (dispatchTrackingIdInput) dispatchTrackingIdInput.value = fallback;
    }
  }

  if (btnGenTrackingId) {
    btnGenTrackingId.addEventListener("click", () => {
      fetchNewTrackingId();
    });
  }

  if (btnCopyTracking) {
    btnCopyTracking.addEventListener("click", () => {
      if (dispatchTrackingIdInput && dispatchTrackingIdInput.value) {
        navigator.clipboard.writeText(dispatchTrackingIdInput.value).then(() => {
          btnCopyTracking.textContent = "✓";
          setTimeout(() => { btnCopyTracking.textContent = "📋"; }, 1500);
        }).catch(() => {});
      }
    });
  }

  // 2. Automated Backend Data Enrichment Preview
  async function updateEnrichmentPreview() {
    // A. Time of Day
    const hour = new Date().getHours();
    let tod = "Afternoon (12-17h)";
    if (hour >= 6 && hour < 12) tod = "Morning (6-12h)";
    else if (hour >= 17 && hour < 22) tod = "Evening (17-22h)";
    else if (hour >= 22 || hour < 6) tod = "Night (22-6h)";
    if (valEnrichTime) valEnrichTime.textContent = tod;

    // B. Live Weather API via Open-Meteo
    try {
      const lat = hotelState.lat || 40.7306;
      const lng = hotelState.lng || -73.9866;
      const res = await fetch(`${API_BASE}/api/weather/live?lat=${lat}&lng=${lng}`);
      if (res.ok) {
        const w = await res.json();
        if (valEnrichWeather) {
          valEnrichWeather.textContent = `${w.weather} (${w.temperature_c}°C)`;
        }
      }
    } catch (_) {
      if (valEnrichWeather) valEnrichWeather.textContent = "Clear (API Connected)";
    }

    // C. Courier Proximity & Availability
    try {
      const activeHotelId = localStorage.getItem("dtml_active_hotel_id");
      const url = activeHotelId ? `${API_BASE}/api/riders?hotel_id=${encodeURIComponent(activeHotelId)}` : `${API_BASE}/api/riders`;
      const res = await fetch(url);
      if (res.ok) {
        const riders = await res.json();
        const availableCount = (riders || []).filter(r => r.status === "Available").length;
        if (valEnrichProximity) {
          valEnrichProximity.textContent = `${availableCount} Available Couriers`;
        }
      }
    } catch (_) {}

    // D. Computed Distance
    if (valEnrichDistance) {
      const d = (distanceInput && distanceInput.value) ? parseFloat(distanceInput.value) : 2.5;
      valEnrichDistance.textContent = `~${d.toFixed(1)} km`;
    }
  }

  // Use Map Dropoff Shortcut Button
  if (btnUseMapAddress) {
    btnUseMapAddress.addEventListener("click", () => {
      if (destinationAddressInput && destinationAddressInput.value) {
        dispatchClientAddressInput.value = destinationAddressInput.value;
      } else {
        dispatchClientAddressInput.value = currentDestinationLabel || "350 5th Ave, Floor 14, New York, NY";
      }
      if (distanceInput && distanceInput.value && valEnrichDistance) {
        valEnrichDistance.textContent = `~${parseFloat(distanceInput.value).toFixed(1)} km`;
      }
    });
  }

  // Jump from Single Prediction to Dispatch
  if (btnGotoDispatch) {
    btnGotoDispatch.addEventListener("click", () => {
      const dispatchTabBtn = document.querySelector(`.tab-btn[data-tab="dispatch-tab"]`);
      if (dispatchTabBtn) dispatchTabBtn.click();
      if (destinationAddressInput && destinationAddressInput.value) {
        dispatchClientAddressInput.value = destinationAddressInput.value;
      }
      if (prepTimeInput && dispatchPrepTimeInput) {
        dispatchPrepTimeInput.value = prepTimeInput.value;
      }
    });
  }

  // 3. 5-Minute Response Window Countdown Timer
  function startCountdownTimer(expiresAtIso) {
    if (countdownTimer) clearInterval(countdownTimer);
    if (!expiresAtIso) return;

    function tick() {
      const targetTime = new Date(expiresAtIso).getTime();
      const now = Date.now();
      const diffMs = targetTime - now;

      if (diffMs <= 0) {
        clearInterval(countdownTimer);
        countdownTimer = null;
        if (cockpitCountdown) {
          cockpitCountdown.textContent = "00:00 (EXPIRED)";
          cockpitCountdown.style.color = "#dc2626";
        }
        if (cockpitStatusChip) {
          cockpitStatusChip.textContent = "Timeout: Auto-Cascading...";
          cockpitStatusChip.className = "dispatch-status-chip chip-timeout";
        }
        handleTimeoutCascade();
        return;
      }

      const totalSec = Math.floor(diffMs / 1000);
      const minutes = Math.floor(totalSec / 60);
      const seconds = totalSec % 60;
      const formatted = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
      if (cockpitCountdown) {
        cockpitCountdown.textContent = formatted;
        if (totalSec < 60) {
          cockpitCountdown.style.color = "#ef4444";
        } else {
          cockpitCountdown.style.color = "";
        }
      }
    }

    tick();
    countdownTimer = setInterval(tick, 1000);
  }

  function stopCountdownTimer() {
    if (countdownTimer) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
  }

  // 4. Render Active Cockpit Session
  function renderCockpitSession(data) {
    if (!data) return;
    activeDispatchSession = data;

    if (cockpitEmptyState) cockpitEmptyState.classList.add("hidden");
    if (cockpitActiveSession) cockpitActiveSession.classList.remove("hidden");

    const trkId = data.tracking_id || (data.order && data.order.tracking_id) || "TRK-000000";
    if (cockpitTrkId) cockpitTrkId.textContent = trkId;

    const rider = data.assigned_rider || (data.order && data.order.assigned_rider) || {};
    if (cockpitRiderName) cockpitRiderName.textContent = rider.rider_name || (data.order && data.order.rider_name) || "Courier Assigned";
    if (cockpitRiderEmail) cockpitRiderEmail.textContent = rider.email || (data.order && data.order.rider_email) || "courier@hub.com";
    if (cockpitRiderAvatar) {
      const v = rider.vehicle_type || (data.order && data.order.vehicle_type) || "Scooter";
      cockpitRiderAvatar.textContent = v === "Car" ? "🚗" : (v === "Bike" ? "🚲" : "🛵");
    }

    const perfScore = rider.performance_score !== undefined ? rider.performance_score : 100;
    const rating = rider.rating || 4.8;
    if (cockpitRiderPerf) {
      cockpitRiderPerf.textContent = `⭐ ${rating.toFixed(1)} • ${Math.round(perfScore)}% On-Time`;
    }

    const distHotel = rider.distance_to_hotel_km !== undefined ? rider.distance_to_hotel_km : 0.2;
    const deliveryDist = data.distance_km || (data.order && data.order.distance_km) || 2.5;
    const etaMin = data.predicted_eta_min || data.predicted_eta_minutes || (data.order && (data.order.predicted_eta_min || data.order.predicted_eta_minutes)) || 25;
    const attempt = data.attempt_count || (data.order && data.order.dispatch_attempts) || 1;

    if (cockpitDistHotel) cockpitDistHotel.textContent = `${distHotel.toFixed(1)} km`;
    if (cockpitDeliveryDist) cockpitDeliveryDist.textContent = `${deliveryDist.toFixed(1)} km`;
    if (cockpitPredictedEta) cockpitPredictedEta.textContent = `~${etaMin} min`;
    if (cockpitAttemptCount) cockpitAttemptCount.textContent = `${attempt}`;
    if (cockpitEmailRecipient) {
      const rName = rider.rider_name || (data.order && data.order.rider_name) || 'Courier';
      const rMail = rider.email || (data.order && data.order.rider_email) || 'courier@hub.com';
      cockpitEmailRecipient.textContent = `${rName} (${rMail})`;
    }

    cachedEmailHtml = (data.email_dispatch && data.email_dispatch.html_preview) || data.email_template_html || data.html_preview || "";

    const st = data.dispatch_status || data.status || (data.order && data.order.dispatch_status) || "Pending_Rider";
    const expiresAt = data.token_expires_at || (data.order && data.order.token_expires_at);
    updateCockpitState(st, expiresAt);

    if (inputActualDuration && etaMin) {
      inputActualDuration.value = Math.max(5, Math.round(etaMin - 2));
    }

    if (deliveryResultBanner) deliveryResultBanner.classList.add("hidden");
  }

  function updateCockpitState(status, tokenExpiresAt) {
    if (!cockpitStatusChip) return;

    const s = String(status || "").toLowerCase();
    const isPending = s.includes("pending") || s.includes("await");
    const isAccepted = s === "accepted" || s === "active" || s.includes("delivery");
    const isDelivered = s === "completed" || s === "delivered";

    if (isPending) {
      cockpitStatusChip.textContent = "Awaiting Courier Response";
      cockpitStatusChip.className = "dispatch-status-chip chip-pending";
      if (timeoutTimerWidget) timeoutTimerWidget.classList.remove("hidden");
      if (tokenExpiresAt) startCountdownTimer(tokenExpiresAt);
      if (btnSimActivate) btnSimActivate.disabled = false;
      if (btnSimDeactivate) btnSimDeactivate.disabled = false;
      if (btnSimTimeout) btnSimTimeout.disabled = false;
      if (btnMarkDelivered) btnMarkDelivered.disabled = true;
    } else if (isAccepted) {
      stopCountdownTimer();
      cockpitStatusChip.textContent = "Active: Courier On Delivery";
      cockpitStatusChip.className = "dispatch-status-chip chip-accepted";
      if (cockpitCountdown) {
        cockpitCountdown.textContent = "ACCEPTED";
        cockpitCountdown.style.color = "#059669";
      }
      if (btnSimActivate) btnSimActivate.disabled = true;
      if (btnSimDeactivate) btnSimDeactivate.disabled = true;
      if (btnSimTimeout) btnSimTimeout.disabled = true;
      if (btnMarkDelivered) btnMarkDelivered.disabled = false;
    } else if (isDelivered) {
      stopCountdownTimer();
      cockpitStatusChip.textContent = "Delivered & Scored";
      cockpitStatusChip.className = "dispatch-status-chip chip-completed";
      if (cockpitCountdown) {
        cockpitCountdown.textContent = "DELIVERED";
        cockpitCountdown.style.color = "#10b981";
      }
      if (btnSimActivate) btnSimActivate.disabled = true;
      if (btnSimDeactivate) btnSimDeactivate.disabled = true;
      if (btnSimTimeout) btnSimTimeout.disabled = true;
      if (btnMarkDelivered) btnMarkDelivered.disabled = true;
    }
  }

  // 5. Admin Form Submission (Instant Availability & Proximity Check)
  if (dispatchAdminForm) {
    dispatchAdminForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const trackingId = dispatchTrackingIdInput ? dispatchTrackingIdInput.value.trim() : "";
      const clientName = dispatchClientNameInput ? dispatchClientNameInput.value.trim() : "";
      const clientPhone = dispatchClientPhoneInput ? dispatchClientPhoneInput.value.trim() : "";
      const clientAddress = dispatchClientAddressInput ? dispatchClientAddressInput.value.trim() : "";
      const prepTime = dispatchPrepTimeInput ? parseFloat(dispatchPrepTimeInput.value) || 15 : 15;
      const traffic = dispatchTrafficLevelInput ? dispatchTrafficLevelInput.value : "Medium";

      if (!clientName || !clientPhone || !clientAddress) {
        alert("Please provide the Client Name, Contact Number, and Delivery Address.");
        return;
      }

      const activeHotelId = localStorage.getItem("dtml_active_hotel_id");
      const payload = {
        tracking_id: trackingId || undefined,
        client_name: clientName,
        client_phone: clientPhone,
        client_address: clientAddress,
        delivery_lat: currentDestLat || (hotelState.lat + 0.02),
        delivery_lng: currentDestLng || (hotelState.lng + 0.02),
        prep_time_minutes: prepTime,
        traffic_level: traffic,
      };

      if (activeHotelId) {
        payload.hotel_id = parseInt(activeHotelId, 10);
      }

      if (btnConfirmDispatch) btnConfirmDispatch.disabled = true;
      if (dispatchSpinner) dispatchSpinner.classList.remove("hidden");

      try {
        const headers = { "Content-Type": "application/json" };
        if (activeHotelId) headers["X-Hotel-ID"] = String(activeHotelId);

        const res = await fetch(`${API_BASE}/api/dispatch/create`, {
          method: "POST",
          headers: headers,
          body: JSON.stringify(payload),
        });

        if (res.ok) {
          const data = await res.json();
          renderCockpitSession(data);
          await loadRecentDispatches();
          await loadFleetStats();
          await loadRidersList();
          if (cockpitActiveSession) {
            cockpitActiveSession.scrollIntoView({ behavior: "smooth", block: "nearest" });
          }
        } else {
          const err = await res.json();
          alert(`Dispatch creation failed: ${err.detail || "No available rider or validation error"}`);
        }
      } catch (err) {
        alert(`Network error creating dispatch: ${err.message}`);
      } finally {
        if (btnConfirmDispatch) btnConfirmDispatch.disabled = false;
        if (dispatchSpinner) dispatchSpinner.classList.add("hidden");
      }
    });
  }

  // 6. Action Simulations (Activate, Deactivate, Timeout, Delivered)
  if (btnSimActivate) {
    btnSimActivate.addEventListener("click", async () => {
      const token = activeDispatchSession ? (activeDispatchSession.dispatch_token || activeDispatchSession.token || activeDispatchSession.response_token || (activeDispatchSession.order && activeDispatchSession.order.dispatch_token)) : null;
      if (!token) {
        alert("No active dispatch session available to activate.");
        return;
      }
      btnSimActivate.disabled = true;
      try {
        const res = await fetch(`${API_BASE}/api/dispatch/respond?token=${encodeURIComponent(token)}&action=activate&format=json`);
        if (res.ok) {
          if (activeDispatchSession) {
            activeDispatchSession.dispatch_status = "Active";
            activeDispatchSession.status = "accepted";
          }
          updateCockpitState("accepted");
          await loadRidersList();
          await loadFleetStats();
          await loadRecentDispatches();
          showToastBanner("✅ Order Activated! Courier is now On Delivery.");
        } else {
          const err = await res.json();
          alert(`Could not activate: ${err.detail || err.error || "Activation failed"}`);
        }
      } catch (e) {
        alert(`Error activating order: ${e.message}`);
      } finally {
        btnSimActivate.disabled = false;
      }
    });
  }

  if (btnSimDeactivate) {
    btnSimDeactivate.addEventListener("click", async () => {
      const token = activeDispatchSession ? (activeDispatchSession.dispatch_token || activeDispatchSession.token || activeDispatchSession.response_token || (activeDispatchSession.order && activeDispatchSession.order.dispatch_token)) : null;
      if (!token) {
        alert("No active dispatch session to deactivate.");
        return;
      }
      btnSimDeactivate.disabled = true;
      try {
        const res = await fetch(`${API_BASE}/api/dispatch/respond?token=${encodeURIComponent(token)}&action=deactivate&format=json`);
        if (res.ok) {
          const data = await res.json();
          if (data.cascaded && (data.order || data.next_rider)) {
            const nextOrder = data.order || activeDispatchSession;
            if (data.next_rider) nextOrder.assigned_rider = data.next_rider;
            if (data.email_dispatch) nextOrder.email_dispatch = data.email_dispatch;
            renderCockpitSession(nextOrder);
            showToastBanner(`🔄 Order Deactivated. Automatically cascaded to ${nextOrder.assigned_rider ? nextOrder.assigned_rider.rider_name : 'next courier'}!`);
          } else {
            showToastBanner(data.message || data.reason || "Order Deactivated.");
          }
          await loadRidersList();
          await loadFleetStats();
          await loadRecentDispatches();
        } else {
          const err = await res.json();
          alert(`Could not deactivate: ${err.detail || err.error || "Deactivate failed"}`);
        }
      } catch (e) {
        alert(`Error deactivating order: ${e.message}`);
      } finally {
        btnSimDeactivate.disabled = false;
      }
    });
  }

  async function handleTimeoutCascade() {
    const trkId = activeDispatchSession ? (activeDispatchSession.tracking_id || (activeDispatchSession.order && activeDispatchSession.order.tracking_id)) : null;
    if (!trkId) return;
    try {
      const res = await fetch(`${API_BASE}/api/dispatch/simulate-timeout/${encodeURIComponent(trkId)}`, {
        method: "POST"
      });
      if (res.ok) {
        const data = await res.json();
        if (data.cascaded && (data.order || data.next_rider)) {
          const nextOrder = data.order || activeDispatchSession;
          if (data.next_rider) nextOrder.assigned_rider = data.next_rider;
          if (data.email_dispatch) nextOrder.email_dispatch = data.email_dispatch;
          renderCockpitSession(nextOrder);
          showToastBanner(`⏱️ 5-Minute Timeout: Cascaded to ${data.next_rider ? data.next_rider.rider_name : 'next courier'}!`);
        } else {
          showToastBanner("⏱️ 5-Minute Timeout: All couriers notified or expired.");
        }
        await loadRidersList();
        await loadFleetStats();
        await loadRecentDispatches();
      }
    } catch (e) {
      console.warn("Timeout cascade error:", e);
    }
  }

  if (btnSimTimeout) {
    btnSimTimeout.addEventListener("click", () => {
      if (!activeDispatchSession) return;
      handleTimeoutCascade();
    });
  }

  // 7. Delivery Completion & Performance Recording (ML Feedback)
  if (btnMarkDelivered) {
    btnMarkDelivered.addEventListener("click", async () => {
      const trkId = activeDispatchSession ? (activeDispatchSession.tracking_id || (activeDispatchSession.order && activeDispatchSession.order.tracking_id)) : null;
      if (!trkId) {
        alert("No active dispatch session to complete.");
        return;
      }
      const actualMins = parseFloat(inputActualDuration ? inputActualDuration.value : "20") || 20;
      btnMarkDelivered.disabled = true;

      try {
        const res = await fetch(`${API_BASE}/api/dispatch/complete/${encodeURIComponent(trkId)}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ actual_duration_min: actualMins, actual_delivery_minutes: actualMins }),
        });

        if (res.ok) {
          const data = await res.json();
          updateCockpitState("completed");

          if (deliveryResultBanner) {
            deliveryResultBanner.classList.remove("hidden");
            const isOnTime = data.was_on_time !== undefined ? data.was_on_time : data.on_time;
            const riderPerf = data.rider_performance || {};
            const score = riderPerf.performance_score !== undefined ? riderPerf.performance_score : (data.rider_performance_score || 100);
            const rating = riderPerf.rating || data.rider_rating || 4.9;
            const riderName = (data.order && data.order.assigned_rider) ? data.order.assigned_rider.rider_name : ((data.order && data.order.rider_name) ? data.order.rider_name : "Courier");
            const etaMin = (data.order && (data.order.predicted_eta_min || data.order.predicted_eta_minutes)) || data.predicted_eta_min || 25;

            if (isOnTime) {
              deliveryResultBanner.className = "delivery-result-banner banner-success";
              deliveryResultBanner.innerHTML = `
                <strong>🏆 On-Time Delivery Recorded!</strong>
                <p>Courier <strong>${riderName}</strong> delivered in <strong>${actualMins} min</strong> (within ML ETA of ~${etaMin} min).</p>
                <p class="banner-sub">⭐ High Performance Awarded: Rating upgraded to <strong>${rating} ★</strong>, Performance Score <strong>${score}%</strong>. Assignment priority boosted!</p>
                <p class="banner-sub">📊 Raw operational features logged directly to Machine Learning retraining dataset.</p>
              `;
            } else {
              deliveryResultBanner.className = "delivery-result-banner banner-warning";
              deliveryResultBanner.innerHTML = `
                <strong>⏱️ Delivery Completed (Delayed)</strong>
                <p>Courier <strong>${riderName}</strong> took <strong>${actualMins} min</strong> (ML ETA was ~${etaMin} min).</p>
                <p class="banner-sub">Courier metrics updated: Rating <strong>${rating} ★</strong>, Score <strong>${score}%</strong>.</p>
                <p class="banner-sub">📊 Raw operational features logged directly to Machine Learning retraining dataset.</p>
              `;
            }
          }

          await loadRidersList();
          await loadFleetStats();
          await loadRecentDispatches();
          await loadRawMlData();
        } else {
          const err = await res.json();
          alert(`Could not complete delivery: ${err.detail || err.error || "Completion failed"}`);
        }
      } catch (e) {
        alert(`Error recording delivery: ${e.message}`);
      } finally {
        btnMarkDelivered.disabled = false;
      }
    });
  }

  function showToastBanner(msg) {
    if (deliveryResultBanner) {
      deliveryResultBanner.classList.remove("hidden");
      deliveryResultBanner.className = "delivery-result-banner banner-info";
      deliveryResultBanner.innerHTML = `<span>${msg}</span>`;
      setTimeout(() => {
        if (deliveryResultBanner && deliveryResultBanner.classList.contains("banner-info")) {
          deliveryResultBanner.classList.add("hidden");
        }
      }, 5000);
    }
  }

  // 8. Email Template Preview Modal
  if (btnPreviewEmailModal) {
    btnPreviewEmailModal.addEventListener("click", () => {
      if (!cachedEmailHtml) {
        alert("No email template has been generated yet for this session.");
        return;
      }
      if (emailIframeWrapper) {
        emailIframeWrapper.innerHTML = cachedEmailHtml;

        // Intercept action clicks inside the email preview
        const links = emailIframeWrapper.querySelectorAll("a");
        links.forEach(a => {
          const href = a.getAttribute("href") || "";
          if (href.includes("action=activate")) {
            a.addEventListener("click", (evt) => {
              evt.preventDefault();
              closeEmailModal();
              if (btnSimActivate) btnSimActivate.click();
            });
          } else if (href.includes("action=deactivate")) {
            a.addEventListener("click", (evt) => {
              evt.preventDefault();
              closeEmailModal();
              if (btnSimDeactivate) btnSimDeactivate.click();
            });
          }
        });
      }
      if (emailPreviewModal) emailPreviewModal.classList.remove("hidden");
    });
  }

  function closeEmailModal() {
    if (emailPreviewModal) emailPreviewModal.classList.add("hidden");
  }

  if (btnCloseEmailModal) btnCloseEmailModal.addEventListener("click", closeEmailModal);

  // Close email modal on backdrop click
  if (emailPreviewModal) {
    emailPreviewModal.addEventListener("click", (e) => {
      if (e.target === emailPreviewModal) closeEmailModal();
    });
  }

  // 9. Tables: Recent Dispatches & Raw ML Retraining Dataset
  if (subtabActiveOrders && subtabRawMl) {
    subtabActiveOrders.addEventListener("click", () => {
      subtabActiveOrders.classList.add("active");
      subtabRawMl.classList.remove("active");
      if (viewActiveOrders) viewActiveOrders.classList.remove("hidden");
      if (viewRawMl) viewRawMl.classList.add("hidden");
    });

    subtabRawMl.addEventListener("click", () => {
      subtabRawMl.classList.add("active");
      subtabActiveOrders.classList.remove("active");
      if (viewRawMl) viewRawMl.classList.remove("hidden");
      if (viewActiveOrders) viewActiveOrders.classList.add("hidden");
      loadRawMlData();
    });
  }

  if (btnToggleRawMl) {
    btnToggleRawMl.addEventListener("click", () => {
      if (subtabRawMl) subtabRawMl.click();
      if (viewRawMl) viewRawMl.scrollIntoView({ behavior: "smooth" });
    });
  }

  if (btnRefreshDispatches) {
    btnRefreshDispatches.addEventListener("click", async () => {
      btnRefreshDispatches.textContent = "⏳ Refreshing...";
      await loadRecentDispatches();
      await loadRawMlData();
      await updateEnrichmentPreview();
      btnRefreshDispatches.textContent = "🔄 Refresh Pipeline";
    });
  }

  async function loadRecentDispatches() {
    try {
      const activeHotelId = localStorage.getItem("dtml_active_hotel_id");
      const url = activeHotelId ? `${API_BASE}/api/dispatch/active?hotel_id=${encodeURIComponent(activeHotelId)}` : `${API_BASE}/api/dispatch/active`;
      const res = await fetch(url);
      if (!res.ok) return;

      const data = await res.json();
      const orders = data.orders || data.active_orders || [];

      if (dispatchCountBadge) dispatchCountBadge.textContent = orders.length;
      if (bnavDispatchBadge) bnavDispatchBadge.textContent = orders.length;
      if (dispatchTableCount) dispatchTableCount.textContent = orders.length;

      if (!dispatchesTableBody) return;

      if (orders.length === 0) {
        dispatchesTableBody.innerHTML = `<tr><td colspan="10" class="empty-cell">No dispatch records found. Create an order above to launch pipeline.</td></tr>`;
        return;
      }

      dispatchesTableBody.innerHTML = "";
      orders.forEach((o) => {
        const tr = document.createElement("tr");

        const st = String(o.dispatch_status || o.status || "").toLowerCase();
        let statusClass = "chip-pending";
        let statusLabel = "Awaiting Response";
        if (st === "accepted" || st === "active" || st.includes("delivery")) {
          statusClass = "chip-accepted";
          statusLabel = "On Delivery";
        } else if (st === "completed" || st === "delivered") {
          statusClass = "chip-completed";
          statusLabel = "Delivered";
        } else if (st === "cascaded" || st.includes("timeout")) {
          statusClass = "chip-timeout";
          statusLabel = "Cascaded";
        }

        const riderName = (o.assigned_rider && o.assigned_rider.rider_name) ? o.assigned_rider.rider_name : (o.rider_name || "Pending");
        const riderDist = o.assigned_rider ? `${(o.assigned_rider.distance_to_hotel_km || 0).toFixed(1)} km` : (o.rider_dist_km ? `${o.rider_dist_km.toFixed(1)} km` : "--");
        const eta = o.predicted_eta_min || o.predicted_eta_minutes || "--";
        const attempts = o.dispatch_attempts || o.attempt_count || 1;

        tr.innerHTML = `
          <td><strong style="font-family:'JetBrains Mono',monospace; color:var(--primary);">${o.tracking_id}</strong></td>
          <td>${o.client_name || '--'}</td>
          <td><a href="tel:${o.client_phone || ''}" style="color:var(--text-main); font-weight:600;">${o.client_phone || '--'}</a></td>
          <td><strong>${riderName}</strong> <span style="font-size:0.75rem; color:var(--text-muted);">(${riderDist})</span></td>
          <td>${(o.distance_km || 0).toFixed(1)} km</td>
          <td><span class="weather-pill">${o.weather || 'Clear'}</span></td>
          <td><strong style="color:var(--primary);">~${eta} min</strong></td>
          <td><span class="attempt-badge">#${attempts}</span></td>
          <td><span class="dispatch-status-chip ${statusClass}" style="padding:0.2rem 0.5rem; font-size:0.75rem;">${statusLabel}</span></td>
          <td>
            <button type="button" class="btn btn-secondary btn-sm btn-inspect-dispatch" data-tracking="${o.tracking_id}" style="padding:0.2rem 0.6rem; font-size:0.75rem;">
              Inspect
            </button>
          </td>
        `;

        const inspectBtn = tr.querySelector(".btn-inspect-dispatch");
        if (inspectBtn) {
          inspectBtn.addEventListener("click", () => {
            renderCockpitSession(o);
            if (cockpitActiveSession) cockpitActiveSession.scrollIntoView({ behavior: "smooth" });
          });
        }

        dispatchesTableBody.appendChild(tr);
      });
    } catch (e) {
      console.warn("Could not load recent dispatches:", e);
    }
  }

  async function loadRawMlData() {
    try {
      const activeHotelId = localStorage.getItem("dtml_active_hotel_id");
      const url = activeHotelId ? `${API_BASE}/api/dispatch/raw-ml-data?hotel_id=${encodeURIComponent(activeHotelId)}` : `${API_BASE}/api/dispatch/raw-ml-data`;
      const res = await fetch(url);
      if (!res.ok) return;

      const data = await res.json();
      const records = data.records || data.raw_records || [];

      if (rawMlTableCount) rawMlTableCount.textContent = records.length;
      if (!rawMlTableBody) return;

      if (records.length === 0) {
        rawMlTableBody.innerHTML = `<tr><td colspan="12" class="empty-cell">No raw ML records logged yet. Complete a delivery to generate retraining records.</td></tr>`;
        return;
      }

      rawMlTableBody.innerHTML = "";
      records.forEach((r) => {
        const tr = document.createElement("tr");
        const isOnTime = r.was_on_time !== undefined ? r.was_on_time : r.on_time;
        const onTimeTag = (isOnTime === 1 || isOnTime === true)
          ? `<span style="color:#059669; font-weight:700;">✅ Yes</span>`
          : (isOnTime === 0 || isOnTime === false ? `<span style="color:#dc2626; font-weight:700;">⏱️ No</span>` : `<span style="color:#64748b;">Pending</span>`);
        
        const loggedDate = (r.completed_at || r.timestamp || r.created_at) ? new Date(r.completed_at || r.timestamp || r.created_at).toLocaleTimeString() : "--";
        const actualMin = r.actual_duration_min !== null && r.actual_duration_min !== undefined
          ? `${r.actual_duration_min}m`
          : (r.actual_delivery_minutes !== null && r.actual_delivery_minutes !== undefined ? `${r.actual_delivery_minutes}m` : '--');
        const predEta = r.predicted_eta_min || r.predicted_eta_minutes || '--';
        const prepMin = r.prep_time_min || r.preparation_time_min || 15;
        const expYrs = r.courier_exp_yrs || r.courier_experience_yrs || 2.5;

        tr.innerHTML = `
          <td><strong style="font-family:'JetBrains Mono',monospace;">${r.tracking_id || '--'}</strong></td>
          <td>${(r.distance_km || 0).toFixed(1)}</td>
          <td>${r.weather || 'Clear'}</td>
          <td>${r.traffic_level || 'Medium'}</td>
          <td>${r.time_of_day || 'Afternoon'}</td>
          <td>${r.vehicle_type || 'Scooter'}</td>
          <td>${prepMin}</td>
          <td>${expYrs}</td>
          <td><strong>~${predEta}m</strong></td>
          <td><strong>${actualMin}</strong></td>
          <td>${onTimeTag}</td>
          <td style="font-size:0.75rem; color:var(--text-muted);">${loggedDate}</td>
        `;
        rawMlTableBody.appendChild(tr);
      });
    } catch (e) {
      console.warn("Could not load raw ML data:", e);
    }
  }

  // 10. Export Raw ML Dataset as JSON
  if (btnExportRawMl) {
    btnExportRawMl.addEventListener("click", async () => {
      try {
        const activeHotelId = localStorage.getItem("dtml_active_hotel_id");
        const url = activeHotelId ? `${API_BASE}/api/dispatch/raw-ml-data?hotel_id=${encodeURIComponent(activeHotelId)}` : `${API_BASE}/api/dispatch/raw-ml-data`;
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
          const a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = `delivery_ml_raw_dataset_${Date.now()}.json`;
          a.click();
        }
      } catch (e) {
        alert(`Export failed: ${e.message}`);
      }
    });
  }

  // Initialize hotel profile, riders fleet, dispatches, and history badge on page load
  loadHotelProfile();
  loadOrderHistory(true);
  loadRidersList();
  loadFleetStats();
  fetchNewTrackingId();
  loadRecentDispatches();
});


