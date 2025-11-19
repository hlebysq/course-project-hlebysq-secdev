# Data Flow Diagram (DFD)

```mermaid
flowchart TB
    %% Boundaries
    subgraph Client Boundary
        Client[User Browser]
    end

    subgraph API Boundary
        API[FastAPI App]
    end

    subgraph Data Boundary
        DB[(Entries DB)]
    end

    %% Flows
    Client -- F1: GET/POST/PUT/DELETE /entries --> API
    API -- F2: Validate input --> API
    API -- F3: CRUD operations --> DB
    DB -- F4: Read results --> API
    API -- F5: JSON response --> Client
