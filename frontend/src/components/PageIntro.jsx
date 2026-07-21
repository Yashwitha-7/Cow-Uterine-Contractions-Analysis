import { Card, Typography } from "antd";

const { Title, Paragraph, Text } = Typography;

export default function PageIntro({ title, subtitle, bullets = [] }) {
  return (
    <Card style={{ marginBottom: 16 }}>
      <Title level={3} style={{ marginTop: 0 }}>
        {title}
      </Title>

      {subtitle && <Paragraph>{subtitle}</Paragraph>}

      {bullets.length > 0 && (
        <ul style={{ marginBottom: 0 }}>
          {bullets.map((item) => (
            <li key={item}>
              <Text>{item}</Text>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}