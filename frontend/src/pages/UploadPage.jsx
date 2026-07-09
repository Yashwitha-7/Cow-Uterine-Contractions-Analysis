import { useState } from "react";
import {
  Alert,
  Button,
  Card,
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

const { Dragger } = Upload;
const { Title, Paragraph, Text } = Typography;

export function UploadPage() {
  const [dataType, setDataType] = useState("contractions");
  const [fileList, setFileList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const beforeUpload = (file) => {
    setFileList((current) => [...current, file]);
    return false;
  };

  const onRemove = (file) => {
    setFileList((current) => current.filter((item) => item.uid !== file.uid));
  };

  const onFinish = async (values) => {
    if (fileList.length === 0) {
      message.error("Please upload at least one file.");
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("cow_id", values.cowId);
      formData.append("notes", values.notes || "");

      if (values.calvingDatetime) {
        formData.append("calving_datetime", values.calvingDatetime);
      }

      if (dataType === "contractions") {
        fileList.forEach((file) => {
          formData.append("files", file);
        });

        const response = await apiClient.post("/upload/contractions", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });

        setResult(response.data);
        message.success("Contraction files processed successfully.");
      } else {
        formData.append("file", fileList[0]);

        const response = await apiClient.post("/upload/bolus", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });

        setResult(response.data);
        message.success("Bolus file processed successfully.");
      }
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      message.error("Upload failed.");
      setResult({ error: detail });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card
      style={{
        maxWidth: 980,
        margin: "32px auto",
        borderRadius: 12,
      }}
    >
      <Title level={3}>Upload Cow Data</Title>
      <Paragraph>
        Upload hourly contraction TXT files or bolus Excel files. Raw files are
        saved separately, processed into standardized CSV files, and stored in
        the project database.
      </Paragraph>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
        message="Phase 1 preprocessing only"
        description="This version performs data ingestion, timestamp creation from TXT filenames, standardized storage, and CSV export. It does not correct calibration shifts, synchronize signals, or run contraction analysis yet."
      />

      <Form layout="vertical" onFinish={onFinish}>
        <Form.Item
          label="Cow ID"
          name="cowId"
          rules={[{ required: true, message: "Please enter a cow ID." }]}
        >
          <Input placeholder="Example: 6263 or 6269" />
        </Form.Item>

        <Form.Item label="Data Type" required>
          <Select
            value={dataType}
            onChange={(value) => {
              setDataType(value);
              setFileList([]);
              setResult(null);
            }}
            options={[
              { label: "Contractions", value: "contractions" },
              { label: "Bolus", value: "bolus" },
            ]}
          />
        </Form.Item>

        <Form.Item label="Known Calving Datetime" name="calvingDatetime">
          <Input placeholder="Example: 2026-07-04 01:41:00" />
        </Form.Item>

        <Form.Item label="Notes" name="notes">
          <Input.TextArea
            rows={3}
            placeholder="Optional notes about cow, SD card, device, recording window, or upload batch."
          />
        </Form.Item>

        <Form.Item label="Upload Files" required>
          <Dragger
            multiple={dataType === "contractions"}
            fileList={fileList}
            beforeUpload={beforeUpload}
            onRemove={onRemove}
            accept={dataType === "contractions" ? ".txt" : ".xlsx,.xls,.csv"}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">
              {dataType === "contractions"
                ? "Select or drag hourly TXT contraction files"
                : "Select or drag one bolus Excel file"}
            </p>
            <p className="ant-upload-hint">
              {dataType === "contractions"
                ? "Each TXT filename should contain its start time, for example 260624132830.txt."
                : "Both 10-minute and daily sheets will be stored in the bolus table."}
            </p>
          </Dragger>
        </Form.Item>

        <Space>
          <Button type="primary" htmlType="submit" loading={loading}>
            Process Upload
          </Button>

          <Button
            onClick={() => {
              setFileList([]);
              setResult(null);
            }}
          >
            Clear
          </Button>
        </Space>
      </Form>

      {result && (
        <Card
          style={{
            marginTop: 24,
            background: result.error ? "#fff2f0" : "#f6ffed",
          }}
        >
          {result.error ? (
            <>
              <Title level={5}>Upload Error</Title>
              <Text>{result.error}</Text>
            </>
          ) : (
            <>
              <Title level={5}>Upload Summary</Title>
              <pre style={{ whiteSpace: "pre-wrap" }}>
                {JSON.stringify(result, null, 2)}
              </pre>
            </>
          )}
        </Card>
      )}
    </Card>
  );
}