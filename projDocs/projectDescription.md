# Gym Management Web Application Project

## Project Overview
I want to create a web application project that enables the management of a Gym that provides personal training classes for users. The gym has multiple centers, and there may be trainers who work at only one center or across multiple locations.

The application must be divided into a **Frontend**, a **Backend**, and a **Database**.
- **Frontend**: Developed using **React + Next.js**.
- **Backend**: Built in **Python** and fully API-based, allowing future expansion. **FastAPI** and **Uvicorn** will be used.
- **Database**: **Azure CosmosDB**, which must be accessed using **Azure DefaultCredentials**.

Users will register on the website, but authentication and access control will be managed through **Microsoft Entra External ID**.

The website will be **multi-language**, initially supporting **Spanish and English**.

Although not integrated initially, the platform must support **payment processing via Stripe**.

Email communications will be handled using **Azure Email Communication Service**.

**Monitoring and telemetry** are crucial. All events occurring in the application must be tracked using **Azure Application Insights**. The required libraries are:
- `azure-monitor-opentelemetry`
- `azure-monitor-opentelemetry-exporter`

All **code** in the application must be written in **English**, including comments.

## Project Structure

The project should have a similar structure as follow. You can add any file that you believe is needed, but it's very important to be carefull with the responsabilities of each element, keeping models in models, services in services, routes in routes.... 
```
.devcontainer/
  ├── devcontainer.json
projDocs/
  ├── projectDescription.md
backend/
  ├── models/
  │   ├── mod_booking.py
  │   ├── mod_trainer.py
  │   ├── mod_user.py
  │   ├── mod_admin.py
  ├── schemas/
  │   ├── sch_booking.py
  │   ├── sch_notification.py
  │   ├── sch_payment.py
  │   ├── sch_trainer.py
  │   ├── sch_user.py
  │   ├── sch_admin.py
  ├── dependencies/
  │   ├── dep_booking.py
  │   ├── dep_notification.py
  │   ├── dep_payment.py
  │   ├── dep_trainer.py
  │   ├── dep_user.py
  │   ├── dep_admin.py
  ├── routers/
  │   ├── rou_booking.py
  │   ├── rou_notification.py
  │   ├── rou_payment.py
  │   ├── rou_trainer.py
  │   ├── rou_user.py
  │   ├── rou_admin.py
  ├── services/
  │   ├── svc_booking.py
  │   ├── svc_notification.py
  │   ├── svc_payment.py
  │   ├── svc_trainer.py
  │   ├── svc_user.py
  │   ├── svc_admin.py
  ├── validators/
  │   ├── val_booking.py
  │   ├── val_users.py
  │   ├── val_trainer.py
  │   ├── val_admin.py
  │   ├── val_payment.py
  │   ├── val_notification.py
  ├── configuration/
  │   ├── config.py
  │   ├── database.py
  │   ├── monitor.py
  ├── backmain.py
frontend/
tests/
  ├── test_booking_svc.py
  ├── test_notification_svc.py
  ├── test_payment_svc.py
  ├── test_trainer_svc.py
  ├── test_user_svc.py
.env
requirements.txt
pytest.ini
README.md
```

The **development environment** and all required tools are configured within a **devcontainer**, which is already implemented in the project.

An **`.env` file** exists and contains all necessary environment variables. These variables must be **initialized at the beginning** so that any file can use them. Ideally, we should create a `config.py` file to store all environment variables, making them easily accessible across all components of the application.

We must ensure that this structure remains **consistent**, ensuring that **services do not handle routing**—instead, all routes should be defined in the corresponding files inside the **`routers`** folder.

An **OpenAPI interface** must be created to **document the backend API**, and it should be available at a route like `/docs` upon application startup. This would be based on Swagger Interactive interface.

## User Roles & Features

### **User Stories**
#### **User**
- Can access a **responsive website** to view gym details, trainers, available services, and contact information.
- Can **log in** using email/password or via **Microsoft Entra External ID**.
- Can **book training sessions**.
- Can **check availability** by **center** or **trainer**.
- Can **cancel a session** (at least **24 hours before** the scheduled time) with an optional message.
- Can **send messages** via a web chat to:
  - Trainers of scheduled sessions.
  - Any trainer.
  - Administrators.
- Can **modify a reservation** (at least **24 hours before**) with a message.
- Can **view their training history**, including session details and trainer information.
- Can **make payments** for sessions or enable **recurring payments**.
- Receives **email notifications** when they receive messages via the platform.
- Can view **upcoming scheduled sessions** by **day, week, or month**.
- Receives **reminder notifications** via the platform and email **48 hours before** a session.
- Receives **notifications** if a session is **modified** or **canceled** by a trainer or administrator.
- Receives a **post-session notification** after completing a session.

#### **Trainer**
- Can log in with **email and password**.
- Can **set availability** per **center**, either **daily, weekly, or monthly**.
- Can **view scheduled sessions**:
  - By **day**
  - By **week**
  - By **month**
- Can **view training history**, including session details and users.
- Can **cancel or modify scheduled sessions**.
- Receives **notifications** for **schedule changes and cancellations**.
- Can **send messages** to:
  - Users with scheduled sessions.
  - Administrators.

#### **Administrator**
- Can **view all scheduled sessions**.
- Can **filter sessions** by:
  - **Center**
  - **User**
  - **Trainer**
  - **Day, week, or month**
- Can **send mass messages** to:
  - All users.
  - All trainers.
- Can **send individual messages** to:
  - Any user.
  - Any trainer.
- Can **modify or cancel any reservation**.
- Can **track all reservation changes**.
- Can **view user reservation history**.
- Can **generate monthly invoices** for users, including all reservations.
- Can **track user payments** and **send payment requests**.
- Receives **notifications** for:
  - Messages from users or trainers.
  - Payment transactions.

## Development Plan
The initial focus will be **solely on backend development**.

