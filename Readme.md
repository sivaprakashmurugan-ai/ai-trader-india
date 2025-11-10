\# AI Intraday Trader (India)



This project is a systematic, model-driven paper trading system for the Indian NSE market. It uses machine learning models to make selective, high-conviction trades while respecting strict risk management rules.



\## Setup Instructions



1\.  \*\*Prerequisites:\*\*

&nbsp;   \*   Docker

&nbsp;   \*   Docker Compose



2\.  \*\*Configuration:\*\*

&nbsp;   \*   Copy the `.env.example` file to a new file named `.env`.

&nbsp;   \*   Review and adjust the parameters in the `.env` file as needed.



3\.  \*\*Build and Run the System:\*\*

&nbsp;   \*   Open a terminal in the project's root directory.

&nbsp;   \*   Run the following command to build the Docker images and start all services in the background:

&nbsp;       ```bash

&nbsp;       docker compose up --build -d

&nbsp;       ```



4\.  \*\*Verify Services:\*\*

&nbsp;   \*   \*\*Database:\*\* The PostgreSQL container will start.

&nbsp;   \*   \*\*Ingestor:\*\* This service will begin fetching historical data. You can view its logs with `docker compose logs -f ingestor`.

&nbsp;   \*   \*\*API:\*\* The FastAPI backend will be available at `http://localhost:8000`. Access the interactive documentation at `http://localhost:8000/docs`.

&nbsp;   \*   \*\*Frontend:\*\*

&nbsp;       \*   Navigate to the `frontend` directory: `cd frontend`.

&nbsp;       \*   Install dependencies: `npm install`.

&nbsp;       \*   Start the development server: `npm start`.

&nbsp;       \*   The dashboard will be available at `http://localhost:3000`.



\## Services



\*   `db`: PostgreSQL database.

\*   `api`: FastAPI backend providing REST APIs for the dashboard.

\*   `ingestor`: Python service to fetch live and historical market data.

\*   `trainer`: Python service for training the ML models (runs once on startup).

\*   `agent`: The core trading logic service that makes paper trading decisions.

\*   `frontend`: React-based dashboard to visualize PnL, positions, and trades.

>>>>>>> e350197804e59c3df1a0f0020dade269adaafb7c
