import json
from flask import Flask, render_template, request, redirect, url_for
from database import get_db_connection
from mysql.connector import IntegrityError


app = Flask(__name__)


@app.route("/")
def home():
    # Open one connection to gather the dashboard's summary information.
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Count records in each main section.
        cursor.execute("SELECT COUNT(*) AS total FROM companies")
        company_count = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM jobs")
        job_count = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM applications")
        application_count = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM contacts")
        contact_count = cursor.fetchone()["total"]

        # Count applications grouped by their current status.
        cursor.execute(
            """
            SELECT status, COUNT(*) AS total
            FROM applications
            GROUP BY status
            ORDER BY status
            """
        )
        status_counts = cursor.fetchall()

        # Show the five most recent applications on the dashboard.
        cursor.execute(
            """
            SELECT applications.application_date,
                   applications.status,
                   jobs.job_title,
                   companies.company_name
            FROM applications
            JOIN jobs ON applications.job_id = jobs.job_id
            JOIN companies ON jobs.company_id = companies.company_id
            ORDER BY applications.application_date DESC,
                     applications.application_id DESC
            LIMIT 5
            """
        )
        recent_applications = cursor.fetchall()

        stats = {
            "companies": company_count,
            "jobs": job_count,
            "applications": application_count,
            "contacts": contact_count,
        }

        return render_template(
            "dashboard.html",
            stats=stats,
            status_counts=status_counts,
            recent_applications=recent_applications,
        )
    finally:
        cursor.close()
        connection.close()


@app.route("/companies", methods=["GET", "POST"])
def companies():
    error = (
        "This company cannot be deleted while it has related jobs or contacts."
        if request.args.get("error") == "linked"
        else None
    )

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if request.method == "POST":
            company_name = request.form.get("company_name", "").strip()

            if not company_name:
                error = "Company name is required."
            else:
                values = (
                    company_name,
                    request.form.get("industry", "").strip() or None,
                    request.form.get("website", "").strip() or None,
                    request.form.get("city", "").strip() or None,
                    request.form.get("state", "").strip() or None,
                    request.form.get("notes", "").strip() or None,
                )

                cursor.execute(
                    """
                    INSERT INTO companies
                    (company_name, industry, website, city, state, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    values,
                )
                connection.commit()
                return redirect(url_for("companies"))

        cursor.execute("SELECT * FROM companies ORDER BY company_name")
        company_rows = cursor.fetchall()

        return render_template(
            "companies.html",
            companies=company_rows,
            error=error,
        )
    finally:
        cursor.close()
        connection.close()

@app.route("/companies/<int:company_id>/edit", methods=["GET", "POST"])
def edit_company(company_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if request.method == "POST":
            company_name = request.form.get("company_name", "").strip()

            if not company_name:
                cursor.execute(
                    "SELECT * FROM companies WHERE company_id = %s",
                    (company_id,),
                )
                company = cursor.fetchone()
                return render_template(
                    "company_edit.html",
                    company=company,
                    error="Company name is required.",
                )

            values = (
                company_name,
                request.form.get("industry", "").strip() or None,
                request.form.get("website", "").strip() or None,
                request.form.get("city", "").strip() or None,
                request.form.get("state", "").strip() or None,
                request.form.get("notes", "").strip() or None,
                company_id,
            )

            cursor.execute(
                """
                UPDATE companies
                SET company_name = %s, industry = %s, website = %s,
                    city = %s, state = %s, notes = %s
                WHERE company_id = %s
                """,
                values,
            )
            connection.commit()
            return redirect(url_for("companies"))

        cursor.execute(
            "SELECT * FROM companies WHERE company_id = %s",
            (company_id,),
        )
        company = cursor.fetchone()

        if company is None:
            return "Company not found", 404

        return render_template("company_edit.html", company=company, error=None)
    finally:
        cursor.close()
        connection.close()


@app.route("/companies/<int:company_id>/delete", methods=["POST"])
def delete_company(company_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "DELETE FROM companies WHERE company_id = %s",
            (company_id,),
        )
        connection.commit()
    except IntegrityError:
        connection.rollback()
        return redirect(url_for("companies", error="linked"))
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("companies"))

@app.route("/jobs", methods=["GET", "POST"])
def jobs():
    error = (
        "This job cannot be deleted because it has an application."
        if request.args.get("error") == "linked"
        else None
    )
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if request.method == "POST":
            company_id = request.form.get("company_id", type=int)
            job_title = request.form.get("job_title", "").strip()

            try:
                salary_min = int(request.form["salary_min"]) if request.form.get("salary_min") else None
                salary_max = int(request.form["salary_max"]) if request.form.get("salary_max") else None
            except ValueError:
                salary_min = salary_max = None
                error = "Salary amounts must be whole numbers."

            if not error and (not company_id or not job_title):
                error = "Choose a company and enter a job title."

            if (
                not error
                and salary_min is not None
                and salary_max is not None
                and salary_min > salary_max
            ):
                error = "Minimum salary cannot be greater than maximum salary."

            if not error:
                skill_list = [
                    skill.strip()
                    for skill in request.form.get("requirements", "").split(",")
                    if skill.strip()
                ]

                cursor.execute(
                    """
                    INSERT INTO jobs
                    (company_id, job_title, job_type, salary_min, salary_max,
                     job_url, date_posted, requirements)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        company_id,
                        job_title,
                        request.form.get("job_type") or None,
                        salary_min,
                        salary_max,
                        request.form.get("job_url") or None,
                        request.form.get("date_posted") or None,
                        json.dumps(skill_list),
                    ),
                )
                connection.commit()
                return redirect(url_for("jobs"))

        cursor.execute(
            "SELECT company_id, company_name FROM companies ORDER BY company_name"
        )
        company_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT jobs.*, companies.company_name
            FROM jobs
            JOIN companies ON jobs.company_id = companies.company_id
            ORDER BY jobs.job_title
            """
        )
        job_rows = cursor.fetchall()

        for job in job_rows:
            low = job["salary_min"]
            high = job["salary_max"]

            if low is not None and high is not None:
                job["salary_display"] = f"${low:,} - ${high:,}"
            elif low is not None:
                job["salary_display"] = f"${low:,}+"
            elif high is not None:
                job["salary_display"] = f"Up to ${high:,}"
            else:
                job["salary_display"] = "Not specified"

            raw_skills = job["requirements"]

            if isinstance(raw_skills, str):
                try:
                    job["requirements_list"] = json.loads(raw_skills)
                except json.JSONDecodeError:
                    job["requirements_list"] = []
            elif isinstance(raw_skills, list):
                job["requirements_list"] = raw_skills
            else:
                job["requirements_list"] = []

        return render_template(
            "jobs.html",
            companies=company_rows,
            jobs=job_rows,
            error=error,
        )
    finally:
        cursor.close()
        connection.close()

@app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
def edit_job(job_id):
    error = None
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM jobs WHERE job_id = %s", (job_id,))
        job = cursor.fetchone()

        if job is None:
            return "Job not found", 404

        if request.method == "POST":
            company_id = request.form.get("company_id", type=int)
            job_title = request.form.get("job_title", "").strip()

            try:
                salary_min = (
                    int(request.form["salary_min"])
                    if request.form.get("salary_min")
                    else None
                )
                salary_max = (
                    int(request.form["salary_max"])
                    if request.form.get("salary_max")
                    else None
                )
            except ValueError:
                salary_min = salary_max = None
                error = "Salary amounts must be whole numbers."

            if not error and (not company_id or not job_title):
                error = "Choose a company and enter a job title."

            if (
                not error
                and salary_min is not None
                and salary_max is not None
                and salary_min > salary_max
            ):
                error = "Minimum salary cannot be greater than maximum salary."

            job.update({
                "company_id": company_id,
                "job_title": job_title,
                "job_type": request.form.get("job_type") or None,
                "salary_min": request.form.get("salary_min") or None,
                "salary_max": request.form.get("salary_max") or None,
                "job_url": request.form.get("job_url") or None,
                "date_posted": request.form.get("date_posted") or None,
                "requirements_text": request.form.get("requirements", ""),
            })

            if not error:
                skills = [
                    skill.strip()
                    for skill in request.form.get("requirements", "").split(",")
                    if skill.strip()
                ]

                cursor.execute(
                    """
                    UPDATE jobs
                    SET company_id = %s,
                        job_title = %s,
                        job_type = %s,
                        salary_min = %s,
                        salary_max = %s,
                        job_url = %s,
                        date_posted = %s,
                        requirements = %s
                    WHERE job_id = %s
                    """,
                    (
                        company_id,
                        job_title,
                        request.form.get("job_type") or None,
                        salary_min,
                        salary_max,
                        request.form.get("job_url") or None,
                        request.form.get("date_posted") or None,
                        json.dumps(skills),
                        job_id,
                    ),
                )
                connection.commit()
                return redirect(url_for("jobs"))

        if request.method == "GET":
            raw_skills = job.get("requirements")
            if isinstance(raw_skills, str):
                try:
                    skills = json.loads(raw_skills)
                except json.JSONDecodeError:
                    skills = []
            elif isinstance(raw_skills, list):
                skills = raw_skills
            else:
                skills = []

            job["requirements_text"] = ", ".join(skills)

        cursor.execute(
            "SELECT company_id, company_name FROM companies ORDER BY company_name"
        )
        company_rows = cursor.fetchall()

        return render_template(
            "job_edit.html",
            job=job,
            companies=company_rows,
            error=error,
        )
    finally:
        cursor.close()
        connection.close()


@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
def delete_job(job_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("DELETE FROM jobs WHERE job_id = %s", (job_id,))
        connection.commit()
    except IntegrityError:
        connection.rollback()
        return redirect(url_for("jobs", error="linked"))
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("jobs"))

@app.route("/applications", methods=["GET", "POST"])
def applications():
    # Hold a message if a required field is missing.
    error = None

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if request.method == "POST":
            job_id = request.form.get("job_id", type=int)
            application_date = request.form.get("application_date", "").strip()
            status = request.form.get("status", "Applied")
            resume_version = request.form.get("resume_version", "").strip() or None

            # A checkbox is present in the form only when checked.
            cover_letter_sent = 1 if request.form.get("cover_letter_sent") else 0

            interview_notes = request.form.get("interview_notes", "").strip()

            if not job_id or not application_date:
                error = "Choose a job and enter the application date."
            else:
                # Store interview notes as a JSON object in the database.
                interview_data = (
                    json.dumps({"notes": interview_notes})
                    if interview_notes
                    else None
                )

                cursor.execute(
                    """
                    INSERT INTO applications
                    (job_id, application_date, status, resume_version,
                     cover_letter_sent, interview_data)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        job_id,
                        application_date,
                        status,
                        resume_version,
                        cover_letter_sent,
                        interview_data,
                    ),
                )
                connection.commit()
                return redirect(url_for("applications"))

        # Load jobs for the form's dropdown.
        cursor.execute(
            """
            SELECT jobs.job_id, jobs.job_title, companies.company_name
            FROM jobs
            JOIN companies ON jobs.company_id = companies.company_id
            ORDER BY companies.company_name, jobs.job_title
            """
        )
        job_rows = cursor.fetchall()

        # Load applications with the job and company names for the table.
        cursor.execute(
            """
            SELECT applications.*, jobs.job_title, companies.company_name
            FROM applications
            JOIN jobs ON applications.job_id = jobs.job_id
            JOIN companies ON jobs.company_id = companies.company_id
            ORDER BY applications.application_date DESC
            """
        )
        application_rows = cursor.fetchall()

        # Decode the JSON notes into a simple value for the template.
        for application in application_rows:
            raw_data = application.get("interview_data")

            if isinstance(raw_data, str):
                try:
                    raw_data = json.loads(raw_data)
                except json.JSONDecodeError:
                    raw_data = {}

            if isinstance(raw_data, dict):
                application["interview_notes"] = raw_data.get("notes", "")
            else:
                application["interview_notes"] = ""

        return render_template(
            "applications.html",
            jobs=job_rows,
            applications=application_rows,
            error=error,
        )
    finally:
        cursor.close()
        connection.close()

@app.route("/applications/<int:application_id>/edit", methods=["GET", "POST"])
def edit_application(application_id):
    # Accepted values must match the status ENUM in the database.
    valid_statuses = {
        "Applied", "Screening", "Interview", "Offer", "Rejected", "Withdrawn"
    }
    error = None

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM applications WHERE application_id = %s",
            (application_id,),
        )
        application = cursor.fetchone()

        if application is None:
            return "Application not found", 404

        if request.method == "POST":
            job_id = request.form.get("job_id", type=int)
            application_date = request.form.get("application_date", "").strip()
            status = request.form.get("status", "")
            resume_version = request.form.get("resume_version", "").strip() or None
            cover_letter_sent = 1 if request.form.get("cover_letter_sent") else 0
            interview_notes = request.form.get("interview_notes", "").strip()

            # Keep submitted values in the form if validation fails.
            application.update({
                "job_id": job_id,
                "application_date": application_date,
                "status": status,
                "resume_version": resume_version,
                "cover_letter_sent": cover_letter_sent,
                "interview_notes": interview_notes,
            })

            if not job_id or not application_date:
                error = "Choose a job and enter the application date."
            elif status not in valid_statuses:
                error = "Choose a valid application status."
            else:
                # Save notes as JSON in the interview_data column.
                interview_data = (
                    json.dumps({"notes": interview_notes})
                    if interview_notes
                    else None
                )

                cursor.execute(
                    """
                    UPDATE applications
                    SET job_id = %s,
                        application_date = %s,
                        status = %s,
                        resume_version = %s,
                        cover_letter_sent = %s,
                        interview_data = %s
                    WHERE application_id = %s
                    """,
                    (
                        job_id,
                        application_date,
                        status,
                        resume_version,
                        cover_letter_sent,
                        interview_data,
                        application_id,
                    ),
                )
                connection.commit()
                return redirect(url_for("applications"))

        else:
            # Decode existing interview JSON so the notes appear in the edit form.
            raw_data = application.get("interview_data")

            if isinstance(raw_data, str):
                try:
                    raw_data = json.loads(raw_data)
                except json.JSONDecodeError:
                    raw_data = {}

            application["interview_notes"] = (
                raw_data.get("notes", "")
                if isinstance(raw_data, dict)
                else ""
            )

        # Load jobs for the job-selection dropdown.
        cursor.execute(
            """
            SELECT jobs.job_id, jobs.job_title, companies.company_name
            FROM jobs
            JOIN companies ON jobs.company_id = companies.company_id
            ORDER BY companies.company_name, jobs.job_title
            """
        )
        job_rows = cursor.fetchall()

        return render_template(
            "application_edit.html",
            application=application,
            jobs=job_rows,
            error=error,
        )
    finally:
        cursor.close()
        connection.close()

@app.route("/applications/<int:application_id>/delete", methods=["POST"])
def delete_application(application_id):
    # Delete the selected application from the database.
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "DELETE FROM applications WHERE application_id = %s",
            (application_id,),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    # Return to the application list after deletion.
    return redirect(url_for("applications"))


@app.route("/contacts", methods=["GET", "POST"])
def contacts():
    # Hold a validation message if a required field is missing.
    error = None

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if request.method == "POST":
            company_id = request.form.get("company_id", type=int)
            contact_name = request.form.get("contact_name", "").strip()

            if not company_id or not contact_name:
                error = "Choose a company and enter the contact's name."
            else:
                # Save the contact and its associated company.
                cursor.execute(
                    """
                    INSERT INTO contacts
                    (company_id, contact_name, title, email, phone,
                     linkedin_url, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        company_id,
                        contact_name,
                        request.form.get("title", "").strip() or None,
                        request.form.get("email", "").strip() or None,
                        request.form.get("phone", "").strip() or None,
                        request.form.get("linkedin_url", "").strip() or None,
                        request.form.get("notes", "").strip() or None,
                    ),
                )
                connection.commit()
                return redirect(url_for("contacts"))

        # Load companies for the form's dropdown.
        cursor.execute(
            "SELECT company_id, company_name FROM companies ORDER BY company_name"
        )
        company_rows = cursor.fetchall()

        # Load contacts together with their company names.
        cursor.execute(
            """
            SELECT contacts.*, companies.company_name
            FROM contacts
            JOIN companies ON contacts.company_id = companies.company_id
            ORDER BY contacts.contact_name
            """
        )
        contact_rows = cursor.fetchall()

        return render_template(
            "contacts.html",
            companies=company_rows,
            contacts=contact_rows,
            error=error,
        )
    finally:
        cursor.close()
        connection.close()

@app.route("/contacts/<int:contact_id>/edit", methods=["GET", "POST"])
def edit_contact(contact_id):
    # Load the selected contact and keep its company relationship.
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    error = None

    try:
        cursor.execute(
            "SELECT * FROM contacts WHERE contact_id = %s",
            (contact_id,),
        )
        contact = cursor.fetchone()

        if contact is None:
            return "Contact not found", 404

        if request.method == "POST":
            company_id = request.form.get("company_id", type=int)
            contact_name = request.form.get("contact_name", "").strip()

            # Keep submitted values visible if required fields are missing.
            contact.update({
                "company_id": company_id,
                "contact_name": contact_name,
                "title": request.form.get("title", "").strip() or None,
                "email": request.form.get("email", "").strip() or None,
                "phone": request.form.get("phone", "").strip() or None,
                "linkedin_url": request.form.get("linkedin_url", "").strip() or None,
                "notes": request.form.get("notes", "").strip() or None,
            })

            if not company_id or not contact_name:
                error = "Choose a company and enter the contact's name."
            else:
                cursor.execute(
                    """
                    UPDATE contacts
                    SET company_id = %s,
                        contact_name = %s,
                        title = %s,
                        email = %s,
                        phone = %s,
                        linkedin_url = %s,
                        notes = %s
                    WHERE contact_id = %s
                    """,
                    (
                        company_id,
                        contact_name,
                        contact["title"],
                        contact["email"],
                        contact["phone"],
                        contact["linkedin_url"],
                        contact["notes"],
                        contact_id,
                    ),
                )
                connection.commit()
                return redirect(url_for("contacts"))

        # Load companies for the edit form's dropdown.
        cursor.execute(
            "SELECT company_id, company_name FROM companies ORDER BY company_name"
        )
        company_rows = cursor.fetchall()

        return render_template(
            "contact_edit.html",
            contact=contact,
            companies=company_rows,
            error=error,
        )
    finally:
        cursor.close()
        connection.close()


@app.route("/contacts/<int:contact_id>/delete", methods=["POST"])
def delete_contact(contact_id):
    # Delete the selected contact and return to the contact list.
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "DELETE FROM contacts WHERE contact_id = %s",
            (contact_id,),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("contacts"))

@app.route("/job-match", methods=["GET", "POST"])
def job_match():
    # Keep the submitted skills in the form so they remain visible in results.
    skills_text = ""
    user_skills = set()
    results = []
    error = None
    submitted = request.method == "POST"

    if submitted:
        skills_text = request.form.get("skills", "").strip()

        # Compare skills without regard to letter case or extra spaces.
        user_skills = {
            skill.strip().casefold()
            for skill in skills_text.split(",")
            if skill.strip()
        }

        if not user_skills:
            error = "Enter at least one skill, separated by commas."
        else:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            try:
                # Load all jobs and their company names for matching.
                cursor.execute(
                    """
                    SELECT jobs.job_id, jobs.job_title, jobs.job_type,
                           jobs.job_url, jobs.requirements,
                           companies.company_name
                    FROM jobs
                    JOIN companies ON jobs.company_id = companies.company_id
                    """
                )
                job_rows = cursor.fetchall()

                for job in job_rows:
                    raw_requirements = job.get("requirements")

                    # Decode the JSON requirements stored in MySQL.
                    if isinstance(raw_requirements, str):
                        try:
                            required_skills = json.loads(raw_requirements)
                        except json.JSONDecodeError:
                            required_skills = []
                    elif isinstance(raw_requirements, list):
                        required_skills = raw_requirements
                    else:
                        required_skills = []

                    # Ignore blank entries in the requirements list.
                    required_skills = [
                        skill.strip()
                        for skill in required_skills
                        if isinstance(skill, str) and skill.strip()
                    ]

                    # Keep jobs without requirements visible, but mark them
                    # so the page doesn't present 0% as a calculated match.
                    if not required_skills:
                        job.update({
                            "required_skills": [],
                            "matched_skills": [],
                            "missing_skills": [],
                            "match_percent": 0,
                            "no_requirements": True,
                        })
                    else:
                        matched_skills = [
                            skill for skill in required_skills
                            if skill.casefold() in user_skills
                        ]
                        missing_skills = [
                            skill for skill in required_skills
                            if skill.casefold() not in user_skills
                        ]
                        match_percent = round(
                            len(matched_skills) / len(required_skills) * 100
                        )

                        job.update({
                            "required_skills": required_skills,
                            "matched_skills": matched_skills,
                            "missing_skills": missing_skills,
                            "match_percent": match_percent,
                            "no_requirements": False,
                        })

                    results.append(job)

                # Highest match percentages appear first.
                results.sort(
                    key=lambda job: (
                        job["no_requirements"],
                        -job["match_percent"],
                        job["job_title"].casefold(),
                    )
                )
            finally:
                cursor.close()
                connection.close()

    return render_template(
        "job_match.html",
        skills_text=skills_text,
        results=results,
        error=error,
        submitted=submitted,
    )

if __name__ == "__main__":
    app.run(debug=True)