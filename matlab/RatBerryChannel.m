classdef RatBerryChannel
    %UNTITLED Summary of this class goes here
    %   Detailed explanation goes here
    
    properties
        conn
        name
    end
    
    methods
        function self = RatBerryChannel(host, port, name)
            %UNTITLED Construct an instance of this class
            %   Detailed explanation goes here
            self.name = name;
            self.conn = tcpclient(host, port);
        end
        
        function [self, reply] = run_command(self, command, varargin)

            %METHOD1 Summary of this method goes here
            %   Detailed explanation goes here
            if nargin>2
                assert(numel(varargin)==1, 'too many inputs');
                args = varargin{1};
                assert(strcmp(class(args), 'struct'), "invalid input for argument 'args'");
            end
            args.command = command;
            self.conn.write(jsonencode(args));
            while self.conn.NumBytesAvailable ==0; continue; end
            reply = char(self.conn.read());
        end
    end
end

