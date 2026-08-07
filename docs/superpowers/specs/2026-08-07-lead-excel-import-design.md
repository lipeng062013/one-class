# Lead Excel Import Design

## Goal

Add a reliable Excel import workflow to the lead-management page. The workflow accepts the supplied legacy `.xls` template and `.xlsx` files, extends lead records with the template's business fields, reports row-level outcomes, and is verified by importing a populated 20-row workbook.

## Scope

- Add an import action and result dialog to the existing lead list page.
- Accept one `.xls` or `.xlsx` file up to 5 MB and 1,000 data rows.
- Add a downloadable standard template.
- Extend lead storage, API responses, list display, and detail display with the imported fields.
- Populate the supplied workbook with 20 representative rows and use it for end-to-end verification.
- Keep the existing lead creation and follow-up workflows intact.

## Workbook Contract

The standard template contains these columns in order:

1. `编号`
2. `姓名`
3. `手机号`
4. `学校`
5. `年级`
6. `年龄`
7. `来源渠道`
8. `对应校区`
9. `归属人`
10. `创建人`
11. `备注`

`姓名` and `手机号` are required. `手机号` must be an 11-digit mainland mobile number. `年龄` is optional but, when present, must be an integer from 1 through 99. Other cells may be blank.

## Data Model

The `leads` table gains these nullable or default-empty fields:

- `external_code`: external lead identifier from `编号`; indexed for duplicate lookup.
- `school`: school name.
- `grade`: grade label.
- `age`: integer age.
- `campus`: campus label.
- `imported_creator_name`: original text from `创建人`.

Existing fields remain authoritative for core lead behavior:

- `student_or_parent_name` stores `姓名`.
- `phone` stores `手机号`.
- `source` stores the normalized source code.
- `channel_note` preserves an unrecognized source as `原来源渠道：<value>`.
- `owner_id` stores the matched assignee.
- `notes` stores `备注`.
- `status` defaults to `new`.
- The authenticated importer remains the actor in the activity audit trail.

Startup migration follows the repository's existing idempotent SQLite `ALTER TABLE ADD COLUMN` pattern.

## Source And User Mapping

Source values are trimmed before matching:

| Workbook value | Stored source |
| --- | --- |
| 老带新, 转介绍 | `referral` |
| 大众点评 | `dianping` |
| 微信 | `wechat` |
| 到店 | `walkin` |
| 其他 or blank | `other` |
| Any other text | `other`, with original text in `channel_note` |

`归属人` matches an active user's display name or username. A unique match sets `owner_id`. A missing or ambiguous match does not reject the row: the lead is imported without an owner and the result contains a warning. `创建人` is stored as plain imported text and never overrides the authenticated audit actor.

## Duplicate Rules

A row is skipped as a duplicate when either of these non-empty values already appeared earlier in the same file or exists in the database:

- normalized `手机号`
- normalized `编号`

The first valid occurrence wins. Duplicate rows are not failures and are reported separately with their row number and reason.

## Backend Design

Add a multipart endpoint under the lead router for users with `leads.write` permission. The endpoint validates extension, size, worksheet headers, and row count before importing. Legacy `.xls` parsing uses `xlrd`; `.xlsx` parsing uses `openpyxl`. Both parsers produce the same normalized row structure, and service-layer validation and persistence operate only on that structure.

Valid rows are inserted with a create activity attributed to the authenticated importer. Row validation, duplicate checks, and user-match warnings accumulate independently so one bad row does not block other valid rows. Valid rows commit together after all rows are processed. A file parsing or database-level failure rolls back the entire batch.

The response contains:

- `imported_count`
- `duplicate_count`
- `failed_count`
- `warning_count`
- row-level `details` with row number, category, and message

The existing single-create endpoint remains unchanged apart from supporting the new optional lead fields.

## Frontend Design

The lead page toolbar gains an upload-icon `导入` button beside `新建线索`. It opens an Element Plus dialog with:

- one-file `.xls,.xlsx` selection;
- a `下载导入模板` command;
- file size and row-limit guidance;
- upload progress and disabled states;
- a result summary for imported, duplicate, failed, and warning counts;
- a compact row-detail table showing row number and reason.

After at least one row imports successfully, the dialog triggers a fresh list request and returns pagination to the first page so the new records are visible. Desktop table and mobile cards expose school, grade, campus, and external code without removing existing status and follow-up controls. The lead detail view shows every new field.

## Error Handling

- Missing required headers rejects the file before any row is written.
- Missing name or phone, invalid phone, and invalid age fail only that row.
- Database and in-file duplicates skip only that row.
- Unmatched or ambiguous owner names create warnings and import without an owner.
- Unknown source values import as `other` and preserve the original source text.
- Unsupported files, files larger than 5 MB, and sheets over 1,000 data rows return a clear request-level error.
- Parser or database exceptions return a safe error message and leave the database unchanged.

## Testing

Backend tests cover:

- valid `.xls` import and field mapping;
- valid `.xlsx` import;
- source normalization and unknown-source preservation;
- database and within-file duplicate detection by phone and external code;
- invalid required fields, phone, and age with partial success;
- matched, missing, and ambiguous assignees;
- missing headers, unsupported files, size and row limits;
- permission denial for users without `leads.write`;
- rollback on persistence failure.

Frontend verification includes the existing TypeScript build gate and browser testing at desktop and compact viewports. The end-to-end acceptance test populates the supplied template with 20 unique rows, imports it through the page, confirms all 20 appear with mapped fields, then uploads the same file again and confirms all 20 are reported as duplicates.

## Acceptance Criteria

1. A permitted user can upload the supplied `.xls` template directly from the lead page.
2. The populated 20-row workbook imports 20 valid leads and refreshes the list.
3. Imported fields appear correctly in lead list and detail views.
4. Owner, creator, source, and audit behavior follow the mapping rules above.
5. Row problems produce actionable row-level results without blocking unrelated valid rows.
6. Re-uploading the same workbook creates no duplicates and reports 20 skipped rows.
7. Existing lead CRUD, follow-up, permissions, responsive layouts, and tests continue to work.
