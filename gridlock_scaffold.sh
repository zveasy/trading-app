#!/bin/bash

# Get feature name from user input
read -p "Enter feature name (use dashes, e.g., user-referral-system): " FEATURE_NAME

# Get today's date
DATE=$(date +"%Y-%m-%d")

# Define base path
BASE_DIR="./gridlock_logs/${DATE}_${FEATURE_NAME}"

# Create directories
mkdir -p "$BASE_DIR"

# Create gutcheck.md
cat <<EOF > "${BASE_DIR}/gutcheck.md"
# gutcheck.md  
*GRIDLOCK | Day 1 – Gut Check*

## 1. Feature / Project Name
> ${FEATURE_NAME//-/ }

## 2. What Are We Building? (The One-Sentence Pitch)
> 

## 3. Why Now?
> 

## 4. Owner(s)
- **Tech Lead:**  
- **Developer(s):**  
- **PM/Stakeholder Contact:**  

## 5. Tech Stack & Tools
- Backend: 
- Frontend: 
- Database: 
- Infra: 
- Third-Party:

## 6. Key Inputs & Outputs
- **Inputs:** 
- **Outputs:** 

## 7. Known Unknowns (AKA “What Could Break Us”)
- 

## 8. Success Criteria
- [ ] 
- [ ] 
- [ ] 

## 9. External Dependencies
- 

## 10. Timeline Agreement
- Sprint A (Days 3–7): 
- Sprint B (Days 8–12): 

## 11. Bonus: If We Had 3 More Days...
- 

**Prepared by:** [Your Name]  
**Date:** ${DATE}
EOF

# Confirmation
echo "GRIDLOCK folder created at: ${BASE_DIR}"