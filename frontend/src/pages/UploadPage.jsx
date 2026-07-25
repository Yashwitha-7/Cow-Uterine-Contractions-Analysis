import { useState } from "react";
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  Select,
  Space,
  Typography,
  Upload,
  message,
} from "antd";
import { InboxOutlined } from "@ant-design/icons";
import { apiClient } from "../api/client";
import PageIntro from "../components/PageIntro";

const { Dragger } = Upload;
const { Paragraph, Text } = Typography;

export default function UploadPage() {
  const [fileList, setFileList] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);

  const clearSelectedFiles = () => {
    setFileList([]);
    message.success("Selected files cleared.");
  };

  const onFinish = async (values) => {
    if (fileList.length === 0) {
      message.error("Please select at least one file.");
      return;
    }

    setUploading(true);
    setResult(null);

    try {
      const formData = new FormData();

      formData.append("cow_id", values.cow_id);
      formData.append("notes", values.notes || "");

      if (values.calving_datetime) {
        formData.append(
          "calving_datetime",
          values.calving_datetime.format("YYYY-MM-DDTHH:mm:ss")
          );
        }

      if (values.data_type === "contractions") {
        fileList.forEach((file) => {
          formData.append("files", file.originFileObj);
        });

        const response = await apiClient.post(
          "/upload/contractions",
          formData,
          {
            headers: { "Content-Type": "multipart/form-data" },
          }
        );

        setResult(response.data);
        message.success("Contraction files uploaded successfully.");
      }

      if (values.data_type === "bolus") {
        if (fileList.length > 1) {
          message.error("Please upload only one bolus Excel file at a time.");
          setUploading(false);
          return;
        }

        formData.append("file", fileList[0].originFileObj);

        const response = await apiClient.post("/upload/bolus", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });

        setResult(response.data);
        message.success("Bolus file uploaded successfully.");
      }
    } catch (error) {
      const detail =
        error?.response?.data?.detail ||
        error?.message ||
        "Upload failed. Check backend logs.";

      if (error?.response?.status === 409) {
        message.error("This cow already has this data type uploaded.");
        setResult({
          message: detail,
          status: "duplicate_upload_blocked",
        });
      } else {
        message.error(String(detail));
        setResult({
          message: String(detail),
          status: "upload_failed",
        });
      }
    } finally {
      setUploading(false);
    }
  };

  const uploadProps = {
    multiple: true,
    beforeUpload: () => false,
    fileList,
    onChange: ({ fileList: newFileList }) => {
      setFileList(newFileList);
    },
    onRemove: (file) => {
      setFileList((current) => current.filter((item) => item.uid !== file.uid));
    },
  };

  return (
    <>
      <PageIntro
        title="Upload Data"
        subtitle="Upload raw contraction TXT files or bolus Excel files into the local Hoffmann Lab processing pipeline."
        bullets={[
          "Contraction TXT files are saved under data/raw/cow_<id>/contractions.",
          "Bolus Excel files are saved under data/raw/cow_<id>/bolus.",
          "The backend creates processed CSV and QC files under data/processed/cow_<id>/.",
          "Each cow can have one contraction upload and one bolus upload unless the database is reset.",
        ]}
      />

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title="Important contraction data rule"
        description="The TXT header may show Time Acc.X Acc.Y Acc.Z..., but the Time header is a device bug. The first numeric column is treated as Acc.X, and timestamps are reconstructed from the filename plus sample index."
      />

      <Card title="Upload Raw Data">
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item
            label="Cow ID"
            name="cow_id"
            rules={[{ required: true, message: "Enter cow ID" }]}
          >
            <Input placeholder="Example: 6263" />
          </Form.Item>

          <Form.Item
            label="Data Type"
            name="data_type"
            rules={[{ required: true, message: "Select data type" }]}
          >
            <Select
              options={[
                {
                  value: "contractions",
                  label: "Contractions TXT files",
                },
                {
                  value: "bolus",
                  label: "Bolus Excel file",
                },
              ]}
            />
          </Form.Item>

          <Form.Item label="Known Calving Datetime" name="calving_datetime">
            <DatePicker showTime style={{ width: "100%" }} />
          </Form.Item>

          <Form.Item label="Notes" name="notes">
            <Input.TextArea
              rows={3}
              placeholder="Example: Cow 6263 contraction upload, Cow 6263 bolus upload, known device notes, etc."
            />
          </Form.Item>

          <Form.Item label="Files">
            <Dragger {...uploadProps}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">
                Click or drag files here to upload
              </p>
              <p className="ant-upload-hint">
                Use multiple TXT files for contractions. Use one Excel file for
                bolus.
              </p>
            </Dragger>
          </Form.Item>

          {fileList.length > 0 && (
            <Alert
              type="success"
              showIcon
              style={{ marginBottom: 16 }}
              title={`${fileList.length} file(s) selected`}
              description="Click Upload and Process to send them to the backend, or Clear Selected Files to remove the current selection."
            />
          )}

          <Space>
            <Button type="primary" htmlType="submit" loading={uploading}>
              Upload and Process
            </Button>

            <Button
              danger
              onClick={clearSelectedFiles}
              disabled={fileList.length === 0 || uploading}
            >
              Clear Selected Files
            </Button>
          </Space>
        </Form>
      </Card>

      {result && (
        <Card title="Upload Result" style={{ marginTop: 16 }}>
          <Paragraph>
            <Text strong>Status: </Text>
            {result.status || "success"}
          </Paragraph>

          <Paragraph>
            <Text strong>Message: </Text>
            {result.message}
          </Paragraph>

          <pre
            style={{
              background: "#f6f8fa",
              padding: 12,
              borderRadius: 8,
              overflowX: "auto",
            }}
          >
            {JSON.stringify(result, null, 2)}
          </pre>
        </Card>
      )}
    </>
  );
}