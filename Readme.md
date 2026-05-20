# Unzila Ahsan - Student ID: BSCS24121
## PDC Assignment 4: Building Resilient Distributed Systems

### Repository: PDC-Sp26-BSCS24121-Unzila

### Assignment Overview
This implementation solves **Problem 3 (Fault Tolerance)** using the Circuit Breaker pattern,
and includes bonus implementations of **Problem 1 (Optimistic Locking)** and **Problem 2
(Idempotency Key structure)**.

### Features Implemented
- ✅ **Circuit Breaker Pattern** for LLM API fault tolerance
- ✅ **3-second timeout** prevents thread pool starvation
- ✅ **Fallback cache** serves last successful responses
- ✅ **X-Student-ID header** on all responses (middleware)
- ✅ **Optimistic locking** for document concurrency (bonus)
- ✅ **Comprehensive test suite** demonstrating before/after behavior

### Setup Instructions

#### Prerequisites
- Python 3.9+
- pip

#### Installation
```bash
# Clone repository
git clone <your-repo-url>
cd PDC-Sp26-BSCS24121-Unzila

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt