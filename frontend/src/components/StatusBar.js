import React from 'react';
import {
  PageSection,
  Text,
  TextContent,
  PageSectionVariants
} from '@patternfly/react-core';

function StatusBar({ status }) {
  return (
    <PageSection variant={PageSectionVariants.darker} isFilled={false}>
      <TextContent>
        <Text component="small">
          Status: {status}
        </Text>
      </TextContent>
    </PageSection>
  );
}

export default StatusBar;
